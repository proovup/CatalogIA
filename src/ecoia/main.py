import asyncio
import os
import uuid
import typer
from typing import Optional
import uvicorn
from fastapi import FastAPI
from ecoia.config import settings
from fastapi.middleware.cors import CORSMiddleware
from ecoia.api.endpoints import upload as upload_router
from ecoia.api.endpoints import supplier as supplier_router
from ecoia.api.endpoints import processing as processing_router
from ecoia.api.endpoints import classification as classification_router
from ecoia.api.endpoints import products as products_router
from ecoia.api.endpoints import formats as formats_router
from ecoia.api.endpoints import scraping as scraping_router
from ecoia.api.endpoints import enrichment as enrichment_router
from ecoia.api.endpoints import config as config_router
from ecoia.db.database import SessionLocal
from ecoia.services.upload_service import FileUploadService
from ecoia.services.document_processing_service import DocumentProcessingService
from ecoia.cli.suppliers import suppliers_cli

# CLI App
cli = typer.Typer(
    name="ecoia",
    help="EcoIA Generator CLI tool",
    add_completion=False,
)

# Add subcommands
cli.add_typer(suppliers_cli)

# API App
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_router.router, prefix="/api/v1")
app.include_router(supplier_router.router, prefix="/api/v1")
app.include_router(processing_router.router, prefix="/api/v1")
app.include_router(classification_router.router, prefix="/api/v1")
app.include_router(products_router.router, prefix="/api/v1")
app.include_router(formats_router.router, prefix="/api/v1")
app.include_router(scraping_router.router, prefix="/api/v1")
app.include_router(config_router.router, prefix="/api/v1")
app.include_router(enrichment_router.router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"name": settings.APP_NAME, "version": settings.VERSION, "status": "running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# CLI Commands
@cli.command()
def version():
    """Show the version of the application."""
    typer.echo(f"{settings.APP_NAME} v{settings.VERSION}")


@cli.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind the server to"),
    port: int = typer.Option(8000, help="Port to bind the server to"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
):
    """Start the API server."""
    typer.echo(f"Starting server at http://{host}:{port}")
    uvicorn.run("ecoia.main:app", host=host, port=port, reload=reload)


@cli.command()
def upload(
    file_path: str = typer.Argument(..., help="Path to the file to upload"),
    supplier: Optional[str] = typer.Option(None, help="Supplier ID (UUID)"),
    batch: bool = typer.Option(False, help="Enable batch upload mode"),
    config: Optional[str] = typer.Option(None, help="Path to configuration file"),
):
    """
    Upload a document to the system.
    """
    if not os.path.exists(file_path):
        typer.echo(f"Error: File '{file_path}' not found.", err=True)
        raise typer.Exit(code=1)

    # Local adapter to mimic FastAPI UploadFile
    class LocalUploadFile:
        def __init__(self, path: str):
            self.path = path
            self.filename = os.path.basename(path)
            self.content_type = "application/octet-stream"
            self._file = open(path, "rb")

        async def read(self, size: int = -1) -> bytes:
            return self._file.read(size)

        def close(self):
            self._file.close()

    async def run_upload():
        db = SessionLocal()
        try:
            service = FileUploadService(db)
            supplier_uuid = uuid.UUID(supplier) if supplier else None

            local_file = LocalUploadFile(file_path)
            try:
                typer.echo(f"Uploading {file_path}...")
                doc = await service.save_file(local_file, supplier_id=supplier_uuid)
                typer.echo(f"Success! Document ID: {doc.id}")
                typer.echo(f"Status: {doc.upload_status}")
            finally:
                local_file.close()

        except Exception as e:
            typer.echo(f"Error during upload: {str(e)}", err=True)
            raise typer.Exit(code=1)
        finally:
            db.close()

    asyncio.run(run_upload())


@cli.command()
def process(
    file_path: str = typer.Argument(..., help="Path to the file to process"),
    config: str = typer.Option(..., "--config", "-c", help="Output format YAML"),
    ai_output: Optional[str] = typer.Option(None, "--ai-output", help="Optional AI output JSON to post-process"),
):
    """Parse a document and generate the output format prompt/validation."""
    if not os.path.exists(file_path):
        typer.echo(f"Error: File '{file_path}' not found.", err=True)
        raise typer.Exit(code=1)

    if not os.path.exists(config):
        typer.echo(f"Error: Config file '{config}' not found.", err=True)
        raise typer.Exit(code=1)

    service = DocumentProcessingService()

    ai_payload = None
    if ai_output:
        if not os.path.exists(ai_output):
            typer.echo(f"Error: AI output file '{ai_output}' not found.", err=True)
            raise typer.Exit(code=1)
        ai_payload = service.load_ai_output(ai_output)

    try:
        result = service.process_document(file_path, config, ai_payload)
    except Exception as exc:
        typer.echo(f"Error during processing: {exc}", err=True)
        raise typer.Exit(code=1)

    typer.echo("\n--- Prompt ---")
    typer.echo(result["prompt"])
    typer.echo("\n--- Parsed ---")
    typer.echo(result["parsed"])
    if result["output"] is not None:
        typer.echo("\n--- Output ---")
        typer.echo(result["output"])


if __name__ == "__main__":
    cli()
