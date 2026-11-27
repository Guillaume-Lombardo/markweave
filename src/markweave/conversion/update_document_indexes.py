"""Run a fixed PyUNO export inside the LibreOffice engine's isolated process group."""

from __future__ import annotations

import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path


def export_with_indexes(soffice: str, workspace: Path, pipe_name: str) -> int:
    """Start a private office session, update indexes and export its PDF."""
    uno = import_module("uno")
    local_context = uno.getComponentContext()
    resolver = local_context.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local_context
    )
    no_connection = uno.getClass("com.sun.star.connection.NoConnectException")
    connection = f"pipe,name={pipe_name};urp;StarOffice.ComponentContext"
    office = subprocess.Popen(  # noqa: S603 - fixed arguments and inherited isolation
        [
            soffice,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nofirststartwizard",
            f"-env:UserInstallation={(workspace / 'profile').as_uri()}",
            f"--accept={connection}",
        ],
        close_fds=True,
        umask=0o077,
    )
    try:
        while office.poll() is None:
            try:
                context = resolver.resolve(f"uno:{connection}")
            except no_connection:
                time.sleep(0.05)
            else:
                break
        else:
            return 1

        def property_value(name: str, value: str | bool | int) -> object:
            result = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            result.Name = name
            result.Value = value
            return result

        desktop = context.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", context
        )
        document = desktop.loadComponentFromURL(
            (workspace / "source.docx").as_uri(),
            "_blank",
            0,
            (
                property_value("Hidden", True),
                property_value("ReadOnly", True),
                property_value(
                    "MacroExecutionMode",
                    uno.getConstantByName(
                        "com.sun.star.document.MacroExecMode.NEVER_EXECUTE"
                    ),
                ),
                property_value(
                    "UpdateDocMode",
                    uno.getConstantByName(
                        "com.sun.star.document.UpdateDocMode.NO_UPDATE"
                    ),
                ),
            ),
        )
        if document is None:
            return 1
        try:
            indexes = document.getDocumentIndexes()
            count = indexes.getCount()
            if not count:
                return 1
            for index in range(count):
                indexes.getByIndex(index).update()
            document.storeToURL(
                (workspace / "output" / "source.pdf").as_uri(),
                (property_value("FilterName", "writer_pdf_Export"),),
            )
        finally:
            document.close(True)
        return 0
    finally:
        # The parent adapter also drains the entire group after success, failure,
        # cancellation, or timeout. Keep the child reap on the normal path.
        office.terminate()
        office.wait()


if __name__ == "__main__":
    raise SystemExit(export_with_indexes(sys.argv[1], Path.cwd(), sys.argv[2]))
