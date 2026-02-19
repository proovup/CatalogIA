from typer.testing import CliRunner
from unittest.mock import MagicMock, patch, AsyncMock
from ecoia.main import cli
from ecoia.db.models import Document

runner = CliRunner()


def test_cli_upload_file_not_found():
    result = runner.invoke(cli, ["upload", "non_existent_file.txt"])
    assert result.exit_code == 1
    assert "Error: File 'non_existent_file.txt' not found." in result.stderr


@patch("ecoia.main.SessionLocal")
@patch("ecoia.main.FileUploadService")
@patch("os.path.exists")
@patch("builtins.open")
def test_cli_upload_success(mock_open, mock_exists, MockService, MockSession):
    # Setup mocks
    mock_exists.return_value = True

    mock_db = MagicMock()
    MockSession.return_value = mock_db

    mock_service_instance = MockService.return_value
    mock_doc = MagicMock(spec=Document)
    mock_doc.id = "123"
    mock_doc.upload_status = "completed"
    mock_service_instance.save_file = AsyncMock(return_value=mock_doc)

    # Mock file open context manager
    mock_file = MagicMock()
    # Ensure read returns bytes (even if not strictly used by our mock save_file,
    # it's good practice for the adapter)
    mock_file.read.return_value = b"test content"
    mock_open.return_value.__enter__.return_value = mock_file

    # Run command
    result = runner.invoke(
        cli,
        ["upload", "test.txt", "--supplier", "3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )

    # Assertions
    if result.exit_code != 0:
        print(f"CLI Error: {result.stdout}")
        print(f"CLI Stderr: {result.stderr}")
        if result.exception:
            import traceback

            traceback.print_exception(
                type(result.exception), result.exception, result.exception.__traceback__
            )

    assert result.exit_code == 0
    assert "Uploading test.txt..." in result.stdout
    assert "Success! Document ID: 123" in result.stdout
    assert "Status: completed" in result.stdout

    # Verify service calls
    MockService.assert_called_once_with(mock_db)
    mock_service_instance.save_file.assert_called_once()

    # Verify DB closed
    mock_db.close.assert_called_once()
