import logging
import shlex
from types import MethodType
from subprocess import Popen, PIPE, STDOUT

from ludolph.command import CommandError, command, parameter_required, admin_required
from ludolph.plugins.plugin import LudolphPlugin

logger = logging.getLogger(__name__)


class Commands(LudolphPlugin):
    """
    Create dynamic Ludolph commands associated with real OS commands and scripts.
    """
    def __init__(self, xmpp, config, **kwargs):
        super(Commands, self).__init__(xmpp, config, **kwargs)
        self.init()

    @staticmethod
    def _parse_config_line(name, value):
        """Parse one config value"""
        value = value.strip().split(',')
        cmd = value.pop(0).strip()
        decorators = [command]
        doc = ''

        for i, opt in enumerate(value):
            opt = opt.strip()

            if opt == 'command':
                continue
            if opt == 'admin_required':
                decorators.append(admin_required)
            elif opt.startswith('parameter_required('):
                try:
                    n = int(opt.split('(')[-1][:-1])
                except ValueError:
                    logger.error('Could not parse dynamic command "%s" value "%s"', name, opt)
                    continue
                else:
                    decorators.append(parameter_required(n))
            else:
                doc = ','.join(value[i:]).strip()
                break

        return cmd, decorators, doc

    @staticmethod
    def _get_fun(name, cmd, decorators, doc):
        """Return dynamic function"""
        # noinspection PyProtectedMember
        fun = lambda obj, msg, *args: obj._execute(msg, cmd, *args)
        fun.__name__ = name
        fun.__doc__ = doc

        for decorator in decorators:
            fun = decorator(fun)

        return fun

    def init(self):
        """Initialize commands from config file"""
        logger.debug('Initializing dynamic commands')

        for name, value in self.config.items():
            fun_name = name.strip().replace('-', '_')
            fun = self._get_fun(fun_name, *self._parse_config_line(name, value))

            if fun:
                logger.info('Registering dynamic command: %s', name)
                setattr(self, fun_name, MethodType(fun, self, Commands))
            else:
                logger.error('Dynamic command "%s" could not be registered', name)

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def _execute(self, msg, cmd, *args, **kwargs):
        """Execute a command and return stdout or raise CommandError"""
        try:
            cmd = shlex.split(cmd)
            cmd.extend(map(str, args))
        except Exception as e:
            raise CommandError('Could not parse command parameters')

        logger.info('Running dynamic command: "%s"', ' '.join(cmd))

        try:
            p = Popen(cmd, bufsize=0, close_fds=True, stdout=PIPE, stderr=STDOUT)
            stdout, stderr = p.communicate()
        except Exception as e:
            raise CommandError('Could not run command (%s)' % e)

        if p.returncode == 0:
            return stdout
        else:
            raise CommandError(stdout)