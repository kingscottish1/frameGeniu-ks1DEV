#!/usr/bin/env python3
"""FrameGenius command-line interface — kingscottishDEV N.A.S."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import __version__
from app.models.video import AspectRatio, VideoParams
from app.services import batch as batch_service
from app.services import task as task_service

app = typer.Typer(add_completion=False, no_args_is_help=True, help="FrameGenius CLI")
console = Console()


@app.command()
def version() -> None:
    """Print the product version."""
    console.print(f"FrameGenius [gold1]{__version__}[/gold1]  ·  kingscottishDEV N.A.S")


@app.command()
def generate(
    topic: str = typer.Argument(..., help="Video topic"),
    template: str = typer.Option("motivational", "--template", "-t"),
    aspect: str = typer.Option("9:16", "--aspect", "-a"),
    duration: float = typer.Option(30.0, "--duration", "-d"),
    voice: str = typer.Option("en-US-JennyNeural", "--voice", "-v"),
    language: str = typer.Option("en", "--language", "-l"),
    script: Optional[Path] = typer.Option(None, "--script", help="Use a custom script file"),
    wait: bool = typer.Option(True, "--wait/--no-wait"),
) -> None:
    """Generate a video from a topic."""
    custom = script.read_text(encoding="utf-8") if script else None
    params = VideoParams(
        topic=topic,
        template=template,
        aspect_ratio=AspectRatio(aspect),
        duration=duration,
        voice=voice,
        language=language,
        script_text=custom,
    )
    if wait:
        console.print(f"[bold]Rendering[/bold] «{topic}» …")
        record = task_service.run_sync(params)
    else:
        record = task_service.submit(params)
        console.print(f"Queued [cyan]{record.task_id}[/cyan]")
        return
    if record.state.value == "completed":
        console.print(f"[green]Done[/green]  {record.result.get('video_path')}")
    else:
        console.print(f"[red]Failed[/red]  {record.error}")
        raise typer.Exit(1)


@app.command("batch")
def batch_cmd(
    file: Path = typer.Argument(..., exists=True, help="Text file, one topic per line"),
    template: str = typer.Option("motivational"),
    aspect: str = typer.Option("9:16"),
    duration: float = typer.Option(30.0),
) -> None:
    """Queue many topics from a text file."""
    base = VideoParams(topic="placeholder", template=template, aspect_ratio=AspectRatio(aspect), duration=duration)
    ids = batch_service.submit_file(file, base)
    console.print(f"Queued {len(ids)} jobs")


@app.command("list")
def list_cmd() -> None:
    """List known tasks."""
    table = Table(title="FrameGenius tasks")
    table.add_column("ID")
    table.add_column("State")
    table.add_column("Progress")
    table.add_column("Topic")
    for item in task_service.list_tasks():
        table.add_row(item.task_id, item.state.value, f"{item.progress}%", str(item.params.get("topic", "")))
    console.print(table)


@app.command()
def status(task_id: str) -> None:
    """Show one task as JSON."""
    record = task_service.get_task(task_id)
    if not record:
        console.print("Not found")
        raise typer.Exit(1)
    console.print_json(json.dumps(record.as_public(), ensure_ascii=False))


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0"),
    port: int = typer.Option(8080),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run("main:app", host=host, port=port)


if __name__ == "__main__":
    app()
