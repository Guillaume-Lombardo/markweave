"""The fixed UNO workflow exports only after updating imported indexes."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from markweave.conversion import update_document_indexes

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "case", ["success", "exited", "rejected", "empty", "update-failed"]
)
def test_uno_load_update_export_and_cleanup(
    tmp_path: Path,
    mocker: MockerFixture,
    case: str,
) -> None:
    class NotConnected(Exception):
        pass

    office = mocker.Mock()
    office.poll.side_effect = [None, 1 if case == "exited" else None]
    start = mocker.patch.object(
        update_document_indexes.subprocess, "Popen", return_value=office
    )
    mocker.patch.object(update_document_indexes.time, "sleep")
    uno = mocker.Mock()
    mocker.patch.object(update_document_indexes, "import_module", return_value=uno)
    uno.getClass.return_value = NotConnected
    uno.createUnoStruct.side_effect = lambda _name: SimpleNamespace()
    uno.getConstantByName.side_effect = lambda name: (
        1 if name.endswith("NEVER_EXECUTE") else 0
    )
    resolver = uno.getComponentContext.return_value.ServiceManager.createInstanceWithContext.return_value
    context = mocker.Mock()
    resolver.resolve.side_effect = [NotConnected, context]
    desktop = context.ServiceManager.createInstanceWithContext.return_value
    document = mocker.Mock()
    desktop.loadComponentFromURL.return_value = None if case == "rejected" else document
    indexes = document.getDocumentIndexes.return_value
    indexes.getCount.return_value = 0 if case == "empty" else 2
    if case == "update-failed":
        indexes.getByIndex.return_value.update.side_effect = RuntimeError

    if case == "update-failed":
        with pytest.raises(RuntimeError):
            update_document_indexes.export_with_indexes(
                "/trusted/soffice", tmp_path, "markweave_fixture/uno"
            )
    else:
        assert update_document_indexes.export_with_indexes(
            "/trusted/soffice", tmp_path, "markweave_fixture/uno"
        ) == (0 if case == "success" else 1)

    argv = start.call_args.args[0]
    assert argv[0] == "/trusted/soffice"
    assert argv[-2] == f"-env:UserInstallation={(tmp_path / 'profile').as_uri()}"
    assert (
        argv[-1]
        == "--accept=pipe,name=markweave_fixture/uno;urp;StarOffice.ComponentContext"
    )
    assert start.call_args.kwargs == {"close_fds": True, "umask": 0o077}
    office.terminate.assert_called_once_with()
    office.wait.assert_called_once_with()
    if case in {"success", "empty", "update-failed"}:
        document.close.assert_called_once_with(True)
    if case == "success":
        assert indexes.getByIndex.call_args_list == [mocker.call(0), mocker.call(1)]
        assert indexes.getByIndex.return_value.update.call_count == 2
        assert {
            prop.Name for prop in desktop.loadComponentFromURL.call_args.args[-1]
        } >= {
            "MacroExecutionMode",
            "UpdateDocMode",
        }
        assert (
            document.storeToURL.call_args.args[0]
            == (tmp_path / "output/source.pdf").as_uri()
        )
    else:
        document.storeToURL.assert_not_called()
