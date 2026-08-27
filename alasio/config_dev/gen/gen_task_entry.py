from alasio.codegen.python import CodeGen
from alasio.config_dev.gen.gen_cross import CrossNavGenerator
from alasio.config_dev.parse.base import DefinitionError
from alasio.config_dev.parse.parse_task_entry import TaskEntryInfo, TaskEntryParser
from alasio.ext.cache import cached_property
from alasio.ext.concurrent.threadpool import THREAD_POOL
from alasio.ext.path.atomic import atomic_read_text
from alasio.ext.path.calc import to_python_import
from alasio.logger import logger


class GenTaskEntry(CrossNavGenerator):
    """Generator for {path_config}/_index/task_entry.py."""

    @cached_property
    def task_entry_file(self):
        return self.path_config.joinpath('_index/task_entry.py')

    def start_task_entry_scan(self):
        """
        Start scanning task entry functions in a single background thread.
        Call this at the beginning of codegen, the result is collected
        when generate_task_entry_file() is called at the end of codegen.
        """
        self._task_entry_job = THREAD_POOL.start_thread_soon(self.scan_task_entry)

    def scan_task_entry(self):
        """
        Scan all files and collect task entries, run on background thread

        Returns:
            dict[str, TaskEntryInfo]:
                key: task name
        """
        out = {}
        for file in self._iter_task_entry_files():
            try:
                code = atomic_read_text(file)
            except FileNotFoundError:
                continue
            rel = file.subpath_to(self.root).to_posix()
            parser = TaskEntryParser(file=rel, code=code)
            for info in parser.iter_entry():
                if info.task in out:
                    raise DefinitionError(
                        f'Duplicate task entry: "{info.task}"',
                        file=info.file,
                    )
                out[info.task] = info
        return out

    def _iter_task_entry_files(self):
        """
        Iter .py files under entry.task_entry_folders,
        skipping path segments that start with "_" (e.g. __pycache__, _index)

        Yields:
            PathStr:
        """
        for folder_name in self.entry.task_entry_folders:
            folder = self.root.joinpath(folder_name)
            for file in folder.iter_files(ext='.py', recursive=True):
                rel = file.subpath_to(self.root).to_posix()
                if any(part.startswith('_') for part in rel.split('/')):
                    continue
                yield file

    @cached_property
    def task_entry_data(self) -> "dict[str, TaskEntryInfo]":
        """
        Wait for the scan job and return the result

        Returns:
            dict[str, TaskEntryInfo]:
                key: task name
        """
        return self._task_entry_job.get()

    def generate_task_entry_file(self, gitadd=None):
        """
        Generate {path_config}/_index/task_entry.py

        Always generate the file, even when no task entry is found,
        so that `from ... import TaskEntryGenerated` never fails.
        """
        data = self.task_entry_data
        gen = CodeGen()
        gen.FromImport('alasio.base.scheduler.scheduler').Import('AlasioScheduler')
        # comment the codegen entry to regenerate this file
        if self.alasio:
            gen.CommentCodeGen('module.config.gen')
        else:
            gen.CommentCodeGen('alasio.config_dev.gen_alasio')

        with gen.Class('TaskEntryGenerated').set_inherit('AlasioScheduler'):
            gen.MultilineComment('Task entry functions, generated from @alasio_task() markers')
            if not data:
                gen.Pass()
            for info in sorted(data.values(), key=lambda x: x.task):
                with gen.Def(info.task).set_args('self'):
                    gen.FromImport(to_python_import(info.file)).Import(info.cls)
                    gen.Raw(f'{info.cls}(config=self.config, device=self.device).{info.func}()')
        file = self.task_entry_file
        op = gen.write(file, skip_same=True)
        if op:
            logger.info(f'Write file {file}')
            if gitadd:
                gitadd.stage_add(file)
