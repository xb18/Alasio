import ast
import re

import msgspec

from alasio.config.entry.utils import validate_task_name
from alasio.config_dev.parse.base import DefinitionError
from alasio.ext.cache import cached_property

# regex to fast check whether the code contains the @alasio_task marker,
# to skip files without the marker and avoid ast parse
REGEX_ALASIO_TASK = re.compile(r'@\s*alasio_task\b')


class TaskEntryInfo(msgspec.Struct):
    """
    A task entry method marked with @alasio_task()
    """
    # task name in scheduler, also the generated method name, e.g. "Reward"
    task: str
    # class name that contains the entry method, e.g. "Reward"
    cls: str
    # method name to call, e.g. "run"
    func: str
    # file path relative to mod root, posix style, e.g. "module/reward/reward.py"
    file: str


class TaskEntryParser:
    """
    Parse a python file, find methods decorated with @alasio_task()

    Attributes:
        file (str): File path relative to mod root, posix style, for error reporting
        code (str): Python code text
        nodes (ast.Module): ast parse result, built lazily
    """

    def __init__(self, file, code):
        """
        Args:
            file (str): File path relative to mod root, posix style
            code (str): Python code text
        """
        self.file = file
        self.code = code

    @cached_property
    def nodes(self):
        """
        ast parse result of the code

        Returns:
            ast.Module:

        Raises:
            DefinitionError: On SyntaxError, with file info
        """
        try:
            return ast.parse(self.code)
        except SyntaxError as e:
            raise DefinitionError(
                f'Invalid python syntax: {e.msg}',
                file=self.file,
            ) from e

    def iter_entry(self):
        """
        Iter methods decorated with @alasio_task()

        Fast check with regex first: if the code does not contain the
        @alasio_task marker at all, return directly without ast parse.
        Multiple @alasio_task decorators on the same method are treated
        as multiple tasks pointing to the same entry function, each decorator
        yields one TaskEntryInfo.

        Yields:
            TaskEntryInfo:
        """
        # fast check, skip files without the marker to avoid ast parse
        if not REGEX_ALASIO_TASK.search(self.code):
            return
        for class_node in self.nodes.body:
            if not isinstance(class_node, ast.ClassDef):
                continue
            for node in class_node.body:
                # async method with marker is an error
                if isinstance(node, ast.AsyncFunctionDef):
                    if self._match_alasio_tasks(node):
                        raise DefinitionError(
                            'Async task entry is not supported',
                            file=self.file,
                        )
                    continue
                if not isinstance(node, ast.FunctionDef):
                    continue
                decorators = self._match_alasio_tasks(node)
                if not decorators:
                    continue
                self._check_method_args(node)
                for decorator in decorators:
                    task_name = self._get_task_name(decorator)
                    yield TaskEntryInfo(
                        task=task_name,
                        cls=class_node.name,
                        func=node.name,
                        file=self.file,
                    )

    def _match_alasio_tasks(self, node):
        """
        Find all @alasio_task decorators in the decorator list of the method

        Args:
            node (ast.FunctionDef | ast.AsyncFunctionDef): The method node

        Returns:
            list[ast.Call]: All matched decorator call nodes

        Raises:
            DefinitionError: On bare @alasio_task without task_name argument
        """
        matched = []
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name):
                if decorator.id == 'alasio_task':
                    raise DefinitionError('Missing task_name argument', file=self.file)
            elif isinstance(decorator, ast.Call):
                func = decorator.func
                if isinstance(func, ast.Name) and func.id == 'alasio_task':
                    matched.append(decorator)
        return matched

    def _get_task_name(self, decorator):
        """
        Get task name from the decorator call, must be a string constant

        Args:
            decorator (ast.Call): The matched @alasio_task(...) decorator node

        Returns:
            str: Task name

        Raises:
            DefinitionError: If task_name is not a string constant, or invalid
        """
        if len(decorator.args) > 1:
            raise DefinitionError(
                f'@alasio_task() accepts at most one positional argument, got {len(decorator.args)}',
                file=self.file,
            )
        task_name = None
        if len(decorator.args) == 1:
            task_name = self._parse_task_name_arg(decorator.args[0])
        else:
            for keyword in decorator.keywords:
                if keyword.arg == 'task_name':
                    task_name = self._parse_task_name_arg(keyword.value)
                    break
        if task_name is None:
            raise DefinitionError(
                'Task name must be a string constant, '
                'e.g. @alasio_task("Reward") or @alasio_task(task_name="Reward")',
                file=self.file,
            )
        if not validate_task_name(task_name):
            raise DefinitionError(
                f'Invalid task name: "{task_name}", must match ^[A-Z][a-zA-Z0-9]*$',
                file=self.file,
            )
        return task_name

    @staticmethod
    def _parse_task_name_arg(arg):
        """
        Args:
            arg (ast.AST): The argument node

        Returns:
            str | None: Task name if the argument is a string constant, else None
        """
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
        return None

    def _check_method_args(self, node):
        """
        The generated code calls the method with no arguments,
        so the method must not have required arguments other than self.
        Arguments with default values, *args and **kwargs are allowed.

        Args:
            node (ast.FunctionDef): The method node

        Raises:
            DefinitionError: If the method has required arguments other than self
        """
        args = node.args
        # defaults align to the last len(defaults) arguments of posonlyargs + args
        n_args = len(args.posonlyargs) + len(args.args)
        n_defaults = len(args.defaults)
        required = [
            arg for arg in (args.posonlyargs + args.args)[:n_args - n_defaults]
            if arg.arg != 'self'
        ]
        if required:
            raise DefinitionError(
                'Task entry method must not have required arguments other than self',
                file=self.file,
            )
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            if default is None:
                raise DefinitionError(
                    'Task entry method must not have required arguments other than self',
                    file=self.file,
                )
