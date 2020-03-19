#!/usr/libexec/platform-python
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Shell script tool to run puppet inside of the given container image.
# Uses the config file at /var/lib/container-puppet/container-puppet.json
# as a source for a JSON array of
# [config_volume, puppet_tags, manifest, config_image, [volumes]] settings
# that can be used to generate config files or run ad-hoc puppet modules
# inside of a container.

import glob
import json
import logging
import multiprocessing
import os
import subprocess
import sys
import tempfile
import time

from paunch import runner as containers_runner

PUPPETS = '/usr/share/openstack-puppet/modules/:/usr/share/openstack-puppet/modules/:ro'

logger = None
sh_script = '/var/lib/container-puppet/container-puppet.sh'
container_cli = os.environ.get('CONTAINER_CLI', 'podman')
container_log_stdout_path = os.environ.get('CONTAINER_LOG_STDOUT_PATH',
                                           '/var/log/containers/stdouts')
cli_cmd = '/usr/bin/' + container_cli


def get_logger():
    global logger
    if logger is None:
        logger = logging.getLogger()
        ch = logging.StreamHandler(sys.stdout)
        if os.environ.get('DEBUG') in ['True', 'true']:
            logger.setLevel(logging.DEBUG)
            ch.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
            ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: '
                                      '%(process)s -- %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger


log = get_logger()
log.info('Running container-puppet')

config_volume_prefix = os.path.abspath(os.environ.get('CONFIG_VOLUME_PREFIX',
                                                      '/var/lib/config-data'))
log.debug('CONFIG_VOLUME_PREFIX: %s' % config_volume_prefix)
if not os.path.exists(config_volume_prefix):
    os.makedirs(config_volume_prefix)

if container_cli == 'docker':
    cli_dcmd = ['--volume', PUPPETS]
    env = {}
    RUNNER = containers_runner.DockerRunner(
        'container-puppet', cont_cmd='docker', log=log)
elif container_cli == 'podman':
    # podman doesn't allow relabeling content in /usr and
    # doesn't support named volumes
    cli_dcmd = ['--security-opt', 'label=disable',
                '--volume', PUPPETS]
    # podman need to find dependent binaries that are in environment
    env = {'PATH': os.environ['PATH']}
    RUNNER = containers_runner.PodmanRunner(
        'container-puppet', cont_cmd='podman', log=log)
else:
    log.error('Invalid container_cli: %s' % container_cli)
    sys.exit(1)

# Controls whether puppet is bind mounted in from the host
# NOTE: we require this to support the tarball extracted (Deployment archive)
# puppet modules but our containers now also include puppet-tripleo so we
# could use either
if (os.environ.get('MOUNT_HOST_PUPPET', 'true') == 'true' and
   PUPPETS not in cli_dcmd):
    cli_dcmd.extend(['--volume', PUPPETS])


# this is to match what we do in deployed-server
def short_hostname():
    subproc = subprocess.Popen(['hostname', '-s'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    cmd_stdout, cmd_stderr = subproc.communicate()
    return cmd_stdout.decode('utf-8').rstrip()


def pull_image(name):

    subproc = subprocess.Popen([cli_cmd, 'inspect', name],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               universal_newlines=True)
    cmd_stdout, cmd_stderr = subproc.communicate()
    retval = subproc.returncode
    if retval == 0:
        log.info('Image already exists: %s' % name)
        return

    retval = -1
    count = 0
    log.info('Pulling image: %s' % name)
    while retval != 0:
        count += 1
        subproc = subprocess.Popen([cli_cmd, 'pull', name],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True)

        cmd_stdout, cmd_stderr = subproc.communicate()
        retval = subproc.returncode
        if retval != 0:
            time.sleep(3)
            log.warning('%s pull failed: %s' % (container_cli, cmd_stderr))
            log.warning('retrying pulling image: %s' % name)
        if count >= 5:
            log.error('Failed to pull image: %s' % name)
            break
    if cmd_stdout:
        log.debug(cmd_stdout)
    if cmd_stderr:
        log.debug(cmd_stderr)


def get_config_base(prefix, volume):
    # crawl the volume's path upwards until we find the
    # volume's base, where the hashed config file resides
    path = volume
    base = prefix.rstrip(os.path.sep)
    base_generated = os.path.join(base, 'puppet-generated')
    while path.startswith(prefix):
        dirname = os.path.dirname(path)
        if dirname == base or dirname == base_generated:
            return path
        else:
            path = dirname
    raise ValueError("Could not find config's base for '%s'" % volume)


def match_config_volumes(prefix, config):
    # Match the mounted config volumes - we can't just use the
    # key as e.g "novacomute" consumes config-data/nova
    try:
        volumes = config.get('volumes', [])
    except AttributeError:
        log.error('Error fetching volumes. Prefix: %s - Config: %s' % (prefix, config))
        raise
    return sorted([get_config_base(prefix, v.split(":")[0])
                   for v in volumes if v.startswith(prefix)])


def get_config_hash(config_volume):
    hashfile = "%s.md5sum" % config_volume
    log.debug("Looking for hashfile %s for config_volume %s" % (hashfile, config_volume))
    hash_data = None
    if os.path.isfile(hashfile):
        log.debug("Got hashfile %s for config_volume %s" % (hashfile, config_volume))
        with open(hashfile) as f:
            hash_data = f.read().rstrip()
    return hash_data


def rm_container(name):
    if os.environ.get('SHOW_DIFF', None):
        log.info('Diffing container: %s' % name)
        subproc = subprocess.Popen([cli_cmd, 'diff', name],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True)
        cmd_stdout, cmd_stderr = subproc.communicate()
        if cmd_stdout:
            log.debug(cmd_stdout)
        if cmd_stderr:
            log.debug(cmd_stderr)

    def run_cmd(rm_cli_cmd):
        subproc = subprocess.Popen(rm_cli_cmd,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE,
                                   universal_newlines=True)
        cmd_stdout, cmd_stderr = subproc.communicate()
        if cmd_stdout:
            log.debug(cmd_stdout)
        if cmd_stderr and \
               cmd_stderr != 'Error response from daemon: ' \
               'No such container: {}\n'.format(name):
            log.debug(cmd_stderr)

    log.info('Removing container: %s' % name)
    rm_cli_cmd = [cli_cmd, 'rm']
    rm_cli_cmd.append(name)
    run_cmd(rm_cli_cmd)

    # rm --storage is used as a mitigation of
    # https://github.com/containers/libpod/issues/3906
    # Also look https://bugzilla.redhat.com/show_bug.cgi?id=1747885
    if container_cli == 'podman':
        rm_storage_cli_cmd = [cli_cmd, 'rm', '--storage']
        rm_storage_cli_cmd.append(name)
        run_cmd(rm_storage_cli_cmd)

process_count = int(os.environ.get('PROCESS_COUNT',
                                   multiprocessing.cpu_count()))
config_file = os.environ.get('CONFIG', '/var/lib/container-puppet/container-puppet.json')
log.debug('CONFIG: %s' % config_file)
# If specified, only this config_volume will be used
config_volume_only = os.environ.get('CONFIG_VOLUME', None)
with open(config_file) as f:
    json_data = json.load(f)

# To save time we support configuring 'shared' services at the same
# time. For example configuring all of the heat services
# in a single container pass makes sense and will save some time.
# To support this we merge shared settings together here.
#
# We key off of config_volume as this should be the same for a
# given group of services.  We are also now specifying the container
# in which the services should be configured.  This should match
# in all instances where the volume name is also the same.

configs = {}

for service in (json_data or []):
    if service is None:
        continue
    if isinstance(service, dict):
        service = [
            service.get('config_volume'),
            service.get('puppet_tags'),
            service.get('step_config'),
            service.get('config_image'),
            service.get('volumes', []),
            service.get('privileged', False),
            service.get('keep_container', False),
        ]

    config_volume = service[0] or ''
    puppet_tags = service[1] or ''
    manifest = service[2] or ''
    config_image = service[3] or ''
    volumes = service[4] if len(service) > 4 else []
    privileged = service[5] if len(service) > 5 else False
    keep_container = service[6] if len(service) > 6 else False

    if not manifest or not config_image:
        continue

    log.debug('config_volume %s' % config_volume)
    log.debug('puppet_tags %s' % puppet_tags)
    log.debug('manifest %s' % manifest)
    log.debug('config_image %s' % config_image)
    log.debug('volumes %s' % volumes)
    log.debug('privileged %s' % privileged)
    log.debug('keep_container %s' % keep_container)
    # We key off of config volume for all configs.
    if config_volume in configs:
        # Append puppet tags and manifest.
        log.debug("Existing service, appending puppet tags and manifest")
        if puppet_tags:
            configs[config_volume][1] = '%s,%s' % (configs[config_volume][1],
                                                   puppet_tags)
        if manifest:
            configs[config_volume][2] = '%s\n%s' % (configs[config_volume][2],
                                                    manifest)
        if configs[config_volume][3] != config_image:
            log.warning("Config containers do not match even though"
                        " shared volumes are the same!")
        if volumes:
            configs[config_volume][4].extend(volumes)

    else:
        if not config_volume_only or (config_volume_only == config_volume):
            log.debug("Adding new service")
            configs[config_volume] = service
        else:
            log.debug("Ignoring %s due to $CONFIG_VOLUME=%s" %
                (config_volume, config_volume_only))

log.info('Service compilation completed.')


def mp_puppet_config(*args):
    (config_volume, puppet_tags, manifest, config_image, volumes, privileged, check_mode, keep_container) = args[0]
    log = get_logger()
    log.info('Starting configuration of %s using image %s' %
             (config_volume, config_image))
    log.debug('config_volume %s' % config_volume)
    log.debug('puppet_tags %s' % puppet_tags)
    log.debug('manifest %s' % manifest)
    log.debug('config_image %s' % config_image)
    log.debug('volumes %s' % volumes)
    log.debug('privileged %s' % privileged)
    log.debug('check_mode %s' % check_mode)
    log.debug('keep_container %s' % keep_container)

    with tempfile.NamedTemporaryFile() as tmp_man:
        with open(tmp_man.name, 'w') as man_file:
            man_file.write('include ::tripleo::packages\n')
            man_file.write(manifest)

        uname = RUNNER.unique_container_name('container-puppet-%s' %
                                             config_volume)
        rm_container(uname)
        pull_image(config_image)

        common_dcmd = [cli_cmd, 'run',
                # Using '0' and not 'root' because it seems podman is susceptible to a race condition
                # https://bugzilla.redhat.com/show_bug.cgi?id=1776766 and
                # https://bugs.launchpad.net/tripleo/+bug/1803544 which are still lurking
                # by using a UID we skip the code that parses /etc/passwd entirely and basically
                # paper over this issue
                '--user', '0',
                '--name', uname,
                '--env', 'PUPPET_TAGS=%s' % puppet_tags,
                '--env', 'NAME=%s' % config_volume,
                '--env', 'HOSTNAME=%s' % short_hostname(),
                '--env', 'NO_ARCHIVE=%s' % os.environ.get('NO_ARCHIVE', ''),
                '--env', 'STEP=%s' % os.environ.get('STEP', '6'),
                '--env', 'NET_HOST=%s' % os.environ.get('NET_HOST', 'false'),
                '--env', 'DEBUG=%s' % os.environ.get('DEBUG', 'false'),
                '--volume', '/etc/localtime:/etc/localtime:ro',
                '--volume', '%s:/etc/config.pp:ro' % tmp_man.name,
                '--volume', '/etc/puppet/:/tmp/puppet-etc/:ro',
                # OpenSSL trusted CA injection
                '--volume', '/etc/pki/ca-trust/extracted:/etc/pki/ca-trust/extracted:ro',
                '--volume', '/etc/pki/tls/certs/ca-bundle.crt:/etc/pki/tls/certs/ca-bundle.crt:ro',
                '--volume', '/etc/pki/tls/certs/ca-bundle.trust.crt:/etc/pki/tls/certs/ca-bundle.trust.crt:ro',
                '--volume', '/etc/pki/tls/cert.pem:/etc/pki/tls/cert.pem:ro',
                '--volume', '%s:/var/lib/config-data/:rw' % config_volume_prefix,
                # facter caching
                '--volume', '/var/lib/container-puppet/puppetlabs/facter.conf:/etc/puppetlabs/facter/facter.conf:ro',
                '--volume', '/var/lib/container-puppet/puppetlabs/:/opt/puppetlabs/:ro',
                # Syslog socket for puppet logs
                '--volume', '/dev/log:/dev/log:rw']

        # Remove container by default after the run
        # This should mitigate the "ghost container" issue described here
        # https://bugzilla.redhat.com/show_bug.cgi?id=1747885
        # https://bugs.launchpad.net/tripleo/+bug/1840691
        if not keep_container:
            common_dcmd.append('--rm')
        if privileged:
            common_dcmd.append('--privileged')

        if container_cli == 'podman':
            log_path = os.path.join(container_log_stdout_path, uname)
            logging = ['--log-driver', 'k8s-file',
                       '--log-opt',
                       'path=%s.log' % log_path]
            common_dcmd.extend(logging)
        elif container_cli == 'docker':
            # NOTE(flaper87): Always copy the DOCKER_* environment variables as
            # they contain the access data for the docker daemon.
            for k in filter(lambda k: k.startswith('DOCKER'), os.environ.keys()):
                env[k] = os.environ.get(k)

        common_dcmd += cli_dcmd

        if check_mode:
            common_dcmd.extend([
                '--volume',
                '/etc/puppet/check-mode:/tmp/puppet-check-mode:ro'])

        for volume in volumes:
            if volume:
                common_dcmd.extend(['--volume', volume])

        common_dcmd.extend(['--entrypoint', sh_script])

        if os.environ.get('NET_HOST', 'false') == 'true':
            log.debug('NET_HOST enabled')
            common_dcmd.extend(['--net', 'host', '--volume',
                                '/etc/hosts:/etc/hosts:ro'])
        else:
            log.debug('running without containers Networking')
            common_dcmd.extend(['--net', 'none'])

        # script injection as the last mount to make sure it's accessible
        # https://github.com/containers/libpod/issues/1844
        common_dcmd.extend(['--volume', '%s:%s:ro' % (sh_script, sh_script)])

        common_dcmd.append(config_image)

        # https://github.com/containers/libpod/issues/1844
        # This block will run "container_cli" run 5 times before to fail.
        retval = -1
        count = 0
        log.debug('Running %s command: %s' % (container_cli, ' '.join(common_dcmd)))
        while count < 3:
            count += 1
            subproc = subprocess.Popen(common_dcmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=env,
                                       universal_newlines=True)
            cmd_stdout, cmd_stderr = subproc.communicate()
            retval = subproc.returncode
            # puppet with --detailed-exitcodes will return 0 for success and no changes
            # and 2 for success and resource changes. Other numbers are failures
            if retval in [0, 2]:
                if cmd_stdout:
                    log.debug('%s run succeeded: %s' % (common_dcmd, cmd_stdout))
                if cmd_stderr:
                    log.warning(cmd_stderr)
                # only delete successful runs, for debugging
                rm_container(uname)
                break
            time.sleep(3)
            log.error('%s run failed after %s attempt(s): %s' % (common_dcmd,
                                                                 cmd_stderr,
                                                                 count))
            rm_container(uname)
            log.warning('Retrying running container: %s' % config_volume)
        else:
            if cmd_stdout:
                log.debug(cmd_stdout)
            if cmd_stderr:
                log.debug(cmd_stderr)
            log.error('Failed running container for %s' % config_volume)
        log.info('Finished processing puppet configs for %s' % (config_volume))
        return retval


# Holds all the information for each process to consume.
# Instead of starting them all linearly we run them using a process
# pool.  This creates a list of arguments for the above function
# to consume.
process_map = []

check_mode = int(os.environ.get('CHECK_MODE', 0))
log.debug('CHECK_MODE: %s' % check_mode)

for config_volume in configs:

    service = configs[config_volume]
    puppet_tags = service[1] or ''
    manifest = service[2] or ''
    config_image = service[3] or ''
    volumes = service[4] if len(service) > 4 else []
    privileged = service[5] if len(service) > 5 else False
    keep_container = service[6] if len(service) > 6 else False

    if puppet_tags:
        puppet_tags = "file,file_line,concat,augeas,cron,%s" % puppet_tags
    else:
        puppet_tags = "file,file_line,concat,augeas,cron"

    process_map.append([config_volume, puppet_tags, manifest, config_image,
                        volumes, privileged, check_mode, keep_container])

for p in process_map:
    log.debug('- %s' % p)

# Fire off processes to perform each configuration.  Defaults
# to the number of CPUs on the system.
log.info('Starting multiprocess configuration steps.  Using %d processes.' %
         process_count)
p = multiprocessing.Pool(process_count)
returncodes = list(p.map(mp_puppet_config, process_map))
config_volumes = [pm[0] for pm in process_map]
success = True
for returncode, config_volume in zip(returncodes, config_volumes):
    if returncode not in [0, 2]:
        log.error('ERROR configuring %s' % config_volume)
        success = False


# Update the startup configs with the config hash we generated above
startup_configs = os.environ.get('STARTUP_CONFIG_PATTERN', '/var/lib/tripleo-config/container_startup_config/*/*.json')
log.debug('STARTUP_CONFIG_PATTERN: %s' % startup_configs)
infiles = glob.glob(startup_configs)

for infile in infiles:
    # If the JSON is already hashed, we'll skip it; and a new hashed file will
    # be created if config changed.
    if 'hashed' in infile:
        log.debug('%s skipped, already hashed' % infile)
        continue

    with open(infile) as f:
        infile_data = json.load(f)

    # if the contents of the file is None, we need should just create an empty
    # data set see LP#1828295
    if not infile_data:
        infile_data = {}

    c_name = os.path.splitext(os.path.basename(infile))[0]
    config_volumes = match_config_volumes(config_volume_prefix, infile_data)
    config_hashes = [get_config_hash(volume_path) for volume_path in config_volumes]
    config_hashes = filter(None, config_hashes)
    config_hash = '-'.join(config_hashes)
    if config_hash:
        log.debug("Updating config hash for %s, config_volume=%s hash=%s" % (c_name, config_volume, config_hash))
        # When python 27 support is removed, we will be able to use z = {**x, **y} to merge the dicts.
        if infile_data.get('environment', None) is None:
            infile_data['environment'] = {}
        infile_data['environment'].update(
            {'TRIPLEO_CONFIG_HASH': config_hash}
        )

    outfile = os.path.join(os.path.dirname(infile), "hashed-" + os.path.basename(infile))
    with open(outfile, 'w') as out_f:
        os.chmod(out_f.name, 0o600)
        json.dump(infile_data, out_f, indent=2)

if not success:
    sys.exit(1)
