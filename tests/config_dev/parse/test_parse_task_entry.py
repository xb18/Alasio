import ast

import pytest

from alasio.config_dev.parse.base import DefinitionError
from alasio.config_dev.parse.parse_task_entry import REGEX_ALASIO_TASK, TaskEntryInfo, TaskEntryParser

CODE_REWARD = """
from alasio.base.scheduler.task_entry import alasio_task


class Reward:
    @alasio_task('Reward')
    def run(self):
        # actual implement
        ...
"""


def iter_entry(code, file='module/reward/reward.py'):
    """
    Parse code and collect task entries

    Args:
        code (str): Python code text
        file (str): File path relative to mod root, posix style

    Returns:
        list[TaskEntryInfo]:
    """
    parser = TaskEntryParser(file=file, code=code)
    return list(parser.iter_entry())


class TestTaskEntryParserBasic:
    """Tests for basic parsing of @alasio_task() markers."""

    def test_positional_argument(self):
        """Positional task name argument is parsed."""
        infos = iter_entry(CODE_REWARD)
        assert infos == [TaskEntryInfo(task='Reward', cls='Reward', func='run', file='module/reward/reward.py')]

    def test_keyword_argument(self):
        """task_name= keyword argument is parsed."""
        code = CODE_REWARD.replace("@alasio_task('Reward')", "@alasio_task(task_name='Reward')")
        infos = iter_entry(code)
        assert infos == [TaskEntryInfo(task='Reward', cls='Reward', func='run', file='module/reward/reward.py')]

    def test_multiple_methods_in_one_class(self):
        """One class can have multiple task entry methods."""
        code = """
class OpsiCampaignRun:
    @alasio_task('OpsiExplore')
    def opsi_explore(self):
        ...

    @alasio_task('OpsiShop')
    def opsi_shop(self):
        ...
"""
        infos = iter_entry(code)
        assert infos == [
            TaskEntryInfo(task='OpsiExplore', cls='OpsiCampaignRun', func='opsi_explore', file='module/reward/reward.py'),
            TaskEntryInfo(task='OpsiShop', cls='OpsiCampaignRun', func='opsi_shop', file='module/reward/reward.py'),
        ]

    def test_multiple_classes(self):
        """Multiple classes in one file each yield their own entries."""
        code = """
class Reward:
    @alasio_task('Reward')
    def run(self):
        ...


class Shop:
    @alasio_task('Shop')
    def run(self):
        ...
"""
        infos = iter_entry(code)
        assert infos == [
            TaskEntryInfo(task='Reward', cls='Reward', func='run', file='module/reward/reward.py'),
            TaskEntryInfo(task='Shop', cls='Shop', func='run', file='module/reward/reward.py'),
        ]

    def test_no_marker_returns_empty(self):
        """A file without any marker yields nothing."""
        code = """
class Reward:
    def run(self):
        ...
"""
        assert iter_entry(code) == []


class TestTaskEntryParserNodes:
    """Tests for the lazily built ast.Module."""

    def test_nodes_is_ast_module(self):
        """nodes is an ast.Module."""
        parser = TaskEntryParser(file='module/reward/reward.py', code=CODE_REWARD)
        assert isinstance(parser.nodes, ast.Module)

    def test_nodes_built_lazily(self):
        """nodes is not parsed until first accessed."""
        parser = TaskEntryParser(file='module/reward/reward.py', code=CODE_REWARD)
        assert 'nodes' not in parser.__dict__
        _ = parser.nodes
        assert 'nodes' in parser.__dict__

    def test_syntax_error_with_marker(self):
        """SyntaxError is converted to DefinitionError with file info."""
        code = '@alasio_task("Reward")\nclass Broken(:\n'
        parser = TaskEntryParser(file='module/reward/reward.py', code=code)
        with pytest.raises(DefinitionError) as e:
            list(parser.iter_entry())
        assert 'Invalid python syntax' in str(e.value)
        assert e.value.file == 'module/reward/reward.py'


class TestTaskEntryParserFastCheck:
    """Tests for the regex fast check that runs before ast parse."""

    def test_valid_code_without_marker(self):
        """Valid code without the marker returns empty."""
        code = """
class Reward:
    def run(self):
        ...
"""
        assert iter_entry(code) == []

    def test_syntax_error_without_marker_no_error(self):
        """Syntax error code without the marker returns empty, no error raised."""
        code = 'def broken(:\n'
        assert iter_entry(code) == []

    def test_syntax_error_with_marker_raises(self):
        """Syntax error code with the marker raises DefinitionError."""
        code = '@alasio_task("Reward")\ndef broken(:\n'
        with pytest.raises(DefinitionError):
            iter_entry(code)

    def test_marker_in_comment_false_positive(self):
        """Marker in a comment hits the fast check but parses fine."""
        code = """
# @alasio_task('Reward')
class Reward:
    def run(self):
        ...
"""
        assert iter_entry(code) == []

    def test_marker_in_string_false_positive(self):
        """Marker in a string hits the fast check but parses fine."""
        code = """
text = '@alasio_task("Reward")'


class Reward:
    def run(self):
        ...
"""
        assert iter_entry(code) == []

    @pytest.mark.parametrize('code', [
        # similar name, no word boundary
        """
class Reward:
    @alasio_taskx('Reward')
    def run(self):
        ...
""",
        # alias
        """
class Reward:
    @at('Reward')
    def run(self):
        ...
""",
        # attribute form
        """
class Reward:
    @xxx.alasio_task('Reward')
    def run(self):
        ...
""",
    ])
    def test_unrecognized_forms_skipped_by_fast_check(self, code):
        """Alias / attribute / similar-name forms are not recognized, fast check misses."""
        assert iter_entry(code) == []


class TestTaskEntryParserIgnore:
    """Tests for markers that must be ignored."""

    def test_other_decorators_mixed(self):
        """Other decorators mixed with the real marker are ignored."""
        code = """
class Reward:
    @other_decorator
    @alasio_task('Reward')
    def run(self):
        ...
"""
        infos = iter_entry(code)
        assert [info.task for info in infos] == ['Reward']

    def test_similar_name_decorator_mixed(self):
        """A similar name decorator next to the real marker is ignored."""
        code = """
class Reward:
    @alasio_taskx
    @alasio_task('Reward')
    def run(self):
        ...
"""
        infos = iter_entry(code)
        assert [info.task for info in infos] == ['Reward']

    def test_module_level_function_ignored(self):
        """Marker on a module-level function is ignored."""
        code = """
@alasio_task('Reward')
def run():
    ...
"""
        assert iter_entry(code) == []

    def test_nested_class_ignored(self):
        """Marker on a method of a nested class is ignored."""
        code = """
class Outer:
    class Inner:
        @alasio_task('Reward')
        def run(self):
            ...
"""
        assert iter_entry(code) == []


class TestTaskEntryParserError:
    """Tests for DefinitionError cases, parametrized."""

    @pytest.mark.parametrize('code', [
        # bare decorator without parentheses
        """
class Reward:
    @alasio_task
    def run(self):
        ...
""",
        # task name is a variable
        """
class Reward:
    name = 'Reward'

    @alasio_task(name)
    def run(self):
        ...
""",
        # task name is an expression
        """
class Reward:
    @alasio_task('Reward' + 'Shop')
    def run(self):
        ...
""",
        # task name is an f-string
        """
class Reward:
    @alasio_task(f'Reward')
    def run(self):
        ...
""",
        # task name is a number
        """
class Reward:
    @alasio_task(123)
    def run(self):
        ...
""",
        # multiple positional arguments
        """
class Reward:
    @alasio_task('Reward', 'Shop')
    def run(self):
        ...
""",
        # required positional argument
        """
class Reward:
    @alasio_task('Reward')
    def run(self, name):
        ...
""",
        # required keyword-only argument
        """
class Reward:
    @alasio_task('Reward')
    def run(self, *, name):
        ...
""",
        # async method
        """
class Reward:
    @alasio_task('Reward')
    async def run(self):
        ...
""",
        # lowercase task name
        """
class Reward:
    @alasio_task('reward')
    def run(self):
        ...
""",
        # underscore in task name
        """
class Reward:
    @alasio_task('Reward_1')
    def run(self):
        ...
""",
        # empty task name
        """
class Reward:
    @alasio_task('')
    def run(self):
        ...
""",
        # digit leading task name
        """
class Reward:
    @alasio_task('1Reward')
    def run(self):
        ...
""",
    ])
    def test_definition_error(self, code):
        """All invalid forms raise DefinitionError."""
        with pytest.raises(DefinitionError):
            iter_entry(code)


class TestTaskEntryParserMethodArgs:
    """Tests for method arguments that are allowed."""

    @pytest.mark.parametrize('method', [
        'def run(self, count=1):',
        'def run(self, count=1, *args):',
        'def run(self, *args):',
        'def run(self, **kwargs):',
        'def run(self, *args, **kwargs):',
        'def run(self, *, count=1):',
    ])
    def test_allowed_method_args(self, method):
        """Methods with default args / *args / **kwargs are allowed."""
        code = f"""
class Reward:
    @alasio_task('Reward')
    {method}
        ...
"""
        infos = iter_entry(code)
        assert infos == [TaskEntryInfo(task='Reward', cls='Reward', func='run', file='module/reward/reward.py')]


class TestTaskEntryParserContract:
    """Tests for the config/device constructor contract (not checked at parse time)."""

    @pytest.mark.parametrize('init', [
        # no __init__, inherit the base class contract
        '',
        # explicit __init__ with config only
        """
    def __init__(self, config):
        self.config = config
""",
        # explicit __init__ with unrelated required arguments
        """
    def __init__(self, foo, bar):
        self.foo = foo
""",
        # overridden __init__ changing the argument list
        """
    def __init__(self, config, device, task):
        self.config = config
""",
    ])
    def test_init_signature_not_checked(self, init):
        """Any __init__ signature is accepted, the contract is runtime only."""
        code = f"""
class Reward:
    {init}
    @alasio_task('Reward')
    def run(self):
        ...
"""
        infos = iter_entry(code)
        assert infos == [TaskEntryInfo(task='Reward', cls='Reward', func='run', file='module/reward/reward.py')]


class TestRegexAlasioTask:
    """Tests for the fast check regex."""

    def test_match_real_marker(self):
        """The real marker always matches, even with spaces after @."""
        assert REGEX_ALASIO_TASK.search('@alasio_task("Reward")')
        assert REGEX_ALASIO_TASK.search('@ alasio_task("Reward")')
        assert REGEX_ALASIO_TASK.search('  @alasio_task("Reward")')

    def test_not_match_similar_name(self):
        """Similar names do not match the word boundary."""
        assert not REGEX_ALASIO_TASK.search('@alasio_taskx("Reward")')
