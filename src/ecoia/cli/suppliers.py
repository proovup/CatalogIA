import json
import os
from typing import Optional
from uuid import UUID
import typer

from ecoia.db.database import SessionLocal
from ecoia.schemas.supplier import SupplierCreate, SupplierUpdate
from ecoia.services.supplier_service import SupplierService
from ecoia.services.config_validator import ConfigValidator

# Supplier CLI commands
suppliers_cli = typer.Typer(name="suppliers", help="Manage supplier configurations")


@suppliers_cli.command("list")
def list_suppliers(
    active_only: bool = typer.Option(
        False, "--active", help="Show only active suppliers"
    )
):
    """List all suppliers"""
    db = SessionLocal()
    try:
        service = SupplierService(db)
        import asyncio

        result = asyncio.run(service.get_suppliers(active_only=active_only))

        if not result.suppliers:
            typer.echo("No suppliers found.")
            return

        typer.echo(f"\n{'ID':<36} {'Name':<25} {'Status':<10} {'Created':<20}")
        typer.echo("-" * 95)

        for supplier in result.suppliers:
            created_str = supplier.created_at.strftime("%Y-%m-%d %H:%M")
            typer.echo(
                f"{str(supplier.id):<36} {supplier.name:<25} "
                f"{supplier.is_active:<10} {created_str:<20}"
            )

        typer.echo(f"\nTotal: {result.total} suppliers")

    finally:
        db.close()


@suppliers_cli.command("show")
def show_supplier(identifier: str = typer.Argument(..., help="Supplier ID or name")):
    """Show supplier details"""
    db = SessionLocal()
    try:
        service = SupplierService(db)
        import asyncio

        try:
            # Try to parse as UUID first
            supplier_id = UUID(identifier)
            supplier = asyncio.run(service.get_supplier(supplier_id))
        except ValueError:
            # Treat as name
            supplier = asyncio.run(service.get_supplier_by_name(identifier))

        typer.echo("\nSupplier Details:")
        typer.echo(f"  ID: {supplier.id}")
        typer.echo(f"  Name: {supplier.name}")
        typer.echo(f"  Description: {supplier.description or 'N/A'}")
        typer.echo(f"  Status: {supplier.is_active}")
        typer.echo(f"  Created: {supplier.created_at}")
        typer.echo(f"  Updated: {supplier.updated_at}")

        if supplier.config:
            typer.echo("\nConfiguration:")
            typer.echo(json.dumps(supplier.config.model_dump(), indent=2))

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        db.close()


@suppliers_cli.command("add")
def add_supplier(
    name: str = typer.Option(..., "--name", "-n", help="Supplier name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Supplier description"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="Configuration file path (JSON)"
    ),
):
    """Add a new supplier"""
    db = SessionLocal()
    try:
        service = SupplierService(db)

        # Load configuration if provided
        config = None
        if config_file:
            if not os.path.exists(config_file):
                typer.echo(f"Error: Config file '{config_file}' not found.", err=True)
                raise typer.Exit(code=1)

            with open(config_file, "r") as f:
                config_dict = json.load(f)

            # Validate configuration
            is_valid, errors = ConfigValidator.validate_config(config_dict)
            if not is_valid:
                typer.echo("Configuration validation failed:", err=True)
                for error in errors:
                    typer.echo(f"  - {error}", err=True)
                raise typer.Exit(code=1)

            from ecoia.schemas.supplier import SupplierConfig

            config = SupplierConfig(**config_dict)

        # Create supplier
        supplier_data = SupplierCreate(
            name=name, description=description, config=config
        )

        import asyncio

        supplier = asyncio.run(service.create_supplier(supplier_data))

        typer.echo("\n✓ Supplier created successfully!")
        typer.echo(f"  ID: {supplier.id}")
        typer.echo(f"  Name: {supplier.name}")

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        db.close()


@suppliers_cli.command("update")
def update_supplier(
    identifier: str = typer.Argument(..., help="Supplier ID or name"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="New description"
    ),
    config_file: Optional[str] = typer.Option(
        None, "--config", "-c", help="New configuration file"
    ),
    status: Optional[str] = typer.Option(
        None, "--status", "-s", help="New status (active/inactive)"
    ),
):
    """Update a supplier"""
    db = SessionLocal()
    try:
        service = SupplierService(db)
        import asyncio

        # Find supplier
        try:
            supplier_id = UUID(identifier)
            existing = asyncio.run(service.get_supplier(supplier_id))
        except ValueError:
            existing = asyncio.run(service.get_supplier_by_name(identifier))

        # Prepare update data
        update_data = SupplierUpdate()
        if name is not None:
            update_data.name = name
        if description is not None:
            update_data.description = description
        if status is not None:
            if status not in ["active", "inactive"]:
                typer.echo("Error: Status must be 'active' or 'inactive'", err=True)
                raise typer.Exit(code=1)
            update_data.is_active = status

        # Load new configuration if provided
        if config_file:
            if not os.path.exists(config_file):
                typer.echo(f"Error: Config file '{config_file}' not found.", err=True)
                raise typer.Exit(code=1)

            with open(config_file, "r") as f:
                config_dict = json.load(f)

            is_valid, errors = ConfigValidator.validate_config(config_dict)
            if not is_valid:
                typer.echo("Configuration validation failed:", err=True)
                for error in errors:
                    typer.echo(f"  - {error}", err=True)
                raise typer.Exit(code=1)

            from ecoia.schemas.supplier import SupplierConfig

            update_data.config = SupplierConfig(**config_dict)

        # Update supplier
        supplier = asyncio.run(service.update_supplier(existing.id, update_data))

        typer.echo("\n✓ Supplier updated successfully!")
        typer.echo(f"  ID: {supplier.id}")
        typer.echo(f"  Name: {supplier.name}")

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        db.close()


@suppliers_cli.command("delete")
def delete_supplier(
    identifier: str = typer.Argument(..., help="Supplier ID or name"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion (soft delete if has documents)"
    ),
):
    """Delete a supplier"""
    db = SessionLocal()
    try:
        service = SupplierService(db)
        import asyncio

        # Find supplier
        try:
            supplier_id = UUID(identifier)
            existing = asyncio.run(service.get_supplier(supplier_id))
        except ValueError:
            existing = asyncio.run(service.get_supplier_by_name(identifier))

        # Confirm deletion
        if not force:
            typer.echo(f"Are you sure you want to delete supplier '{existing.name}'?")
            typer.echo("This action cannot be undone. Use --force to confirm.")
            raise typer.Exit(code=0)

        # Delete supplier
        asyncio.run(service.delete_supplier(existing.id))

        typer.echo(f"\n✓ Supplier '{existing.name}' deleted successfully!")

    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(code=1)
    finally:
        db.close()


@suppliers_cli.command("test-config")
def test_config(
    config_file: str = typer.Argument(..., help="Configuration file path"),
    sample_file: str = typer.Option(
        ..., "--sample", "-s", help="Sample file to test with"
    ),
):
    """Test a supplier configuration with a sample file"""
    # Load configuration
    if not os.path.exists(config_file):
        typer.echo(f"Error: Config file '{config_file}' not found.", err=True)
        raise typer.Exit(code=1)

    if not os.path.exists(sample_file):
        typer.echo(f"Error: Sample file '{sample_file}' not found.", err=True)
        raise typer.Exit(code=1)

    with open(config_file, "r") as f:
        config_dict = json.load(f)

    # Validate configuration
    is_valid, errors = ConfigValidator.validate_config(config_dict)
    if not is_valid:
        typer.echo("Configuration validation failed:", err=True)
        for error in errors:
            typer.echo(f"  - {error}", err=True)
        raise typer.Exit(code=1)

    # Test with sample file
    from ecoia.schemas.supplier import SupplierConfig

    config = SupplierConfig(**config_dict)

    typer.echo(f"\nTesting configuration with sample file: {sample_file}")
    typer.echo("-" * 50)

    valid, errors, warnings, sample_data = ConfigValidator.test_config_with_sample(
        config, sample_file
    )

    if valid:
        typer.echo("✓ Configuration test PASSED\n")
    else:
        typer.echo("✗ Configuration test FAILED\n")

    if errors:
        typer.echo("Errors:")
        for error in errors:
            typer.echo(f"  ✗ {error}", err=True)
        typer.echo()

    if warnings:
        typer.echo("Warnings:")
        for warning in warnings:
            typer.echo(f"  ⚠ {warning}")
        typer.echo()

    if sample_data is not None:
        typer.echo(f"Sample data ({len(sample_data)} rows):")
        typer.echo(sample_data.to_string(index=False))


@suppliers_cli.command("template")
def generate_template(
    file_type: str = typer.Option(
        "csv", "--type", "-t", help="File type (csv, xlsx, xls)"
    ),
    output: str = typer.Option(
        "supplier_config_template.json", "--output", "-o", help="Output file path"
    ),
):
    """Generate a configuration template"""
    template = ConfigValidator.generate_config_template(file_type)

    # Write template to file
    with open(output, "w") as f:
        json.dump(template, f, indent=2)

    typer.echo(f"\n✓ Configuration template generated: {output}")
    typer.echo(f"  File type: {file_type}")
    typer.echo(
        "\nEdit the template to match your supplier's file format and use it with:"
    )
    typer.echo(f"  ecoia suppliers add --config {output} --name <supplier-name>")
