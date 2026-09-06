# src/cli/main.py
# Rich CLI suite for store searching, turn-by-turn routing, store profile inspection, and local server launch.
# Connects to: src/config.py, src/services/google_maps.py, src/services/store_repository.py
# Created: 2026-09-06

import asyncio
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.config import settings
from src.models.directions import TravelMode
from src.models.geo import Coordinates
from src.models.trip import TripPlanRequest
from src.services.google_maps import GoogleMapsService
from src.services.store_repository import StoreRepository
from src.services.trip_exporter import TripExporter
from src.services.trip_planner import TripPlannerService
from src.utils.hours import format_time_12hr

console = Console()


@click.group()
@click.version_option(version=settings.app_version, prog_name="store-locator")
def cli() -> None:
    """Advanced Google Maps Store Locator CLI."""
    pass


@cli.command()
@click.option("--address", "-a", type=str, help="Search address, city, or postal code")
@click.option("--lat", type=float, help="Search latitude in decimal degrees")
@click.option("--lng", type=float, help="Search longitude in decimal degrees")
@click.option("--radius", "-r", type=float, default=25.0, show_default=True, help="Search radius in kilometers")
@click.option("--open-now", is_flag=True, help="Filter for stores currently open")
@click.option("--min-rating", type=float, default=None, help="Filter minimum customer rating (0.0 - 5.0)")
@click.option("--amenity", type=str, default=None, help="Filter by amenity (e.g. drive_thru, ev_charging, curbside_pickup)")
@click.option("--sort", type=click.Choice(["distance", "rating", "name"]), default="distance", show_default=True, help="Sort results by field")
@click.option("--limit", "-n", type=int, default=10, show_default=True, help="Maximum stores to display")
def search(
    address: Optional[str],
    lat: Optional[float],
    lng: Optional[float],
    radius: float,
    open_now: bool,
    min_rating: Optional[float],
    amenity: Optional[str],
    sort: str,
    limit: int,
) -> None:
    """Search for retail store locations nearest to a location."""
    repo = StoreRepository()
    maps = GoogleMapsService()

    # Determine origin
    origin_lat = lat
    origin_lng = lng
    resolved_name = address or ""

    if (origin_lat is None or origin_lng is None) and address:
        with console.status(f"[cyan]Geocoding address: '{address}'...[/cyan]"):
            geo = asyncio.run(maps.geocode(address))
            if not geo:
                console.print(f"[red]Error:[/red] Could not resolve coordinates for '{address}'")
                raise click.Abort()
            origin_lat = geo.coordinates.latitude
            origin_lng = geo.coordinates.longitude
            resolved_name = geo.formatted_address
    elif origin_lat is None or origin_lng is None:
        origin_lat = settings.default_latitude
        origin_lng = settings.default_longitude
        resolved_name = "San Francisco, CA (Default)"

    results = repo.search_nearby(
        latitude=origin_lat,
        longitude=origin_lng,
        radius_km=radius,
        open_now=open_now,
        min_rating=min_rating,
        amenity=amenity,
        sort_by=sort,
        limit=limit,
    )

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Store Proximity Search[/bold green]\n"
            f"[dim]Origin:[/dim] [bold]{resolved_name}[/bold] ({origin_lat:.4f}, {origin_lng:.4f})\n"
            f"[dim]Radius:[/dim] {radius} km | [dim]Open Now Filter:[/dim] {open_now} | [dim]Found:[/dim] {len(results)} stores",
            border_style="green",
        )
    )

    if not results:
        console.print("[yellow]No stores matched your search criteria within the specified radius.[/yellow]\n")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("ID", width=4, justify="right")
    table.add_column("Store Name", style="bold white", min_width=24)
    table.add_column("Distance", justify="right", width=12)
    table.add_column("Status", width=22)
    table.add_column("Rating", width=10, justify="center")
    table.add_column("Key Amenities", style="dim", min_width=20)

    for item in results:
        store = item.store
        status_color = "green" if item.is_open_now else "red"
        status_display = f"[{status_color}]{item.status_text}[/{status_color}]"
        rating_display = f"* {store.rating:.1f} ({store.user_ratings_total})"

        amenities_list = []
        if store.amenities.drive_thru:
            amenities_list.append("Drive-Thru")
        if store.amenities.curbside_pickup:
            amenities_list.append("Curbside")
        if store.amenities.ev_charging:
            amenities_list.append("EV Charging")
        amenities_str = ", ".join(amenities_list) or "Standard"

        table.add_row(
            str(store.id),
            store.name,
            f"{item.distance_miles:.1f} mi ({item.distance_km:.1f} km)",
            status_display,
            rating_display,
            amenities_str,
        )

    console.print(table)
    console.print()


@cli.command()
@click.argument("store_id", type=int)
def get(store_id: int) -> None:
    """View full profile, weekly hours, and reviews for a store."""
    repo = StoreRepository()
    store = repo.get_by_id(store_id)
    if not store:
        console.print(f"[red]Error:[/red] Store ID {store_id} not found.")
        raise click.Abort()

    console.print()
    console.print(
        Panel(
            f"[bold cyan]{store.name}[/bold cyan] [dim]({store.brand})[/dim]\n"
            f"[bold]Address:[/bold] {store.full_address}\n"
            f"[bold]Phone:[/bold] {store.phone or 'N/A'} | [bold]Website:[/bold] {store.website or 'N/A'}\n"
            f"[bold]Rating:[/bold] * {store.rating:.1f} / 5.0 ({store.user_ratings_total} customer reviews)\n"
            f"[bold]Coordinates:[/bold] {store.latitude:.6f}, {store.longitude:.6f}",
            title=f"Store #{store.id}",
            border_style="cyan",
        )
    )

    # Weekly Operating Schedule
    hours_table = Table(title="Weekly Operating Hours", show_header=True, header_style="bold blue")
    hours_table.add_column("Day", style="bold")
    hours_table.add_column("Hours")

    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        dh = store.hours.get_day(day)
        if dh.is_closed:
            val = "[red]Closed[/red]"
        else:
            val = f"{format_time_12hr(dh.open_time)} - {format_time_12hr(dh.close_time)}"
        hours_table.add_row(day.capitalize(), val)

    console.print(hours_table)

    # Amenities
    amenities = store.amenities.model_dump()
    active_amenities = [k.replace("_", " ").title() for k, v in amenities.items() if v]
    console.print(f"\n[bold]Amenities & Services:[/bold] {', '.join(active_amenities)}")

    # Customer Reviews
    if store.reviews:
        console.print("\n[bold]Verified Customer Reviews:[/bold]")
        for rev in store.reviews:
            console.print(f"  * [yellow]* {rev.rating:.1f}[/yellow] [bold]{rev.author_name}[/bold] [dim]({rev.relative_time_description}):[/dim] \"{rev.text}\"")
    console.print()


@cli.command()
@click.option("--from-loc", "-f", "origin_input", required=True, help="Origin address, landmark, or lat,lng")
@click.option("--to-store", "-t", "store_id", type=int, required=True, help="Target store ID")
@click.option("--mode", "-m", type=click.Choice(["driving", "walking", "bicycling", "transit"]), default="driving", show_default=True)
def directions(origin_input: str, store_id: int, mode: str) -> None:
    """Get turn-by-turn navigation directions from an origin to a store."""
    repo = StoreRepository()
    maps = GoogleMapsService()

    store = repo.get_by_id(store_id)
    if not store:
        console.print(f"[red]Error:[/red] Target store ID {store_id} not found.")
        raise click.Abort()

    # Parse origin
    origin_coords: Optional[Coordinates] = None
    origin_name = origin_input

    if "," in origin_input and not any(c.isalpha() for c in origin_input):
        try:
            parts = origin_input.split(",")
            origin_coords = Coordinates(latitude=float(parts[0].strip()), longitude=float(parts[1].strip()))
        except Exception:
            pass

    if origin_coords is None:
        with console.status(f"[cyan]Geocoding origin '{origin_input}'...[/cyan]"):
            geo = asyncio.run(maps.geocode(origin_input))
            if not geo:
                console.print(f"[red]Error:[/red] Could not resolve coordinates for origin '{origin_input}'")
                raise click.Abort()
            origin_coords = geo.coordinates
            origin_name = geo.formatted_address

    travel_mode = TravelMode(mode)
    with console.status(f"[cyan]Calculating {mode} route to {store.name}...[/cyan]"):
        result = asyncio.run(
            maps.directions(
                origin=origin_coords,
                destination=store.coordinates,
                mode=travel_mode,
                origin_name=origin_name,
                destination_name=store.name,
            )
        )

    console.print()
    console.print(
        Panel.fit(
            f"[bold green]Route Directions ({travel_mode.value.capitalize()})[/bold green]\n"
            f"[dim]From:[/dim] [bold]{result.origin_address}[/bold]\n"
            f"[dim]To:[/dim]   [bold]{store.name}[/bold] ({store.street}, {store.city})\n"
            f"[dim]Distance:[/dim] [bold]{result.distance_text}[/bold] ({result.total_distance_km:.1f} km)\n"
            f"[dim]Estimated Duration:[/dim] [bold green]{result.duration_text}[/bold green]",
            border_style="green",
        )
    )

    steps_table = Table(title="Turn-by-Turn Navigation Steps", show_header=True, header_style="bold cyan")
    steps_table.add_column("#", width=3, justify="right")
    steps_table.add_column("Turn Instruction", style="bold white")
    steps_table.add_column("Distance", width=12, justify="right")
    steps_table.add_column("Time", width=10, justify="right")

    for idx, step in enumerate(result.steps, 1):
        steps_table.add_row(str(idx), step.instruction, step.distance_text, step.duration_text)

    console.print(steps_table)
    console.print(f"\n[dim]Overview Polyline:[/dim] [italic]{result.overview_polyline[:36]}...[/italic]\n")


@cli.command("list")
@click.option("--limit", "-n", type=int, default=25, show_default=True, help="Maximum stores to list")
def list_stores(limit: int) -> None:
    """List all registered store locations."""
    repo = StoreRepository()
    stores = repo.list_all(limit=limit)

    table = Table(title=f"Registered Store Locations ({len(stores)} total)", show_header=True, header_style="bold magenta")
    table.add_column("ID", width=4, justify="right")
    table.add_column("Store Name", style="bold")
    table.add_column("City / State", width=20)
    table.add_column("Rating", width=10, justify="center")
    table.add_column("Phone", width=18)

    for s in stores:
        table.add_row(
            str(s.id),
            s.name,
            f"{s.city}, {s.state}",
            f"* {s.rating:.1f}",
            s.phone or "N/A",
        )

    console.print()
    console.print(table)
    console.print()


@cli.command("trip")
@click.option("--origin", "-o", required=True, type=str, help="Starting origin address, city, or 'lat,lng'")
@click.option("--store", "-s", "stores", multiple=True, type=int, required=True, help="Store IDs to visit (repeat -s for multiple)")
@click.option("--round-trip/--one-way", default=True, show_default=True, help="Return to origin after visiting all stores")
@click.option("--optimize/--no-optimize", default=True, show_default=True, help="Apply TSP route optimization")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["driving", "walking", "bicycling", "transit"]),
    default="driving",
    show_default=True,
    help="Travel mode",
)
@click.option("--export-gpx", type=click.Path(writable=True), default=None, help="File path to save route as GPX 1.1")
@click.option("--export-csv", type=click.Path(writable=True), default=None, help="File path to save manifest as CSV")
@click.option("--show-url", is_flag=True, default=True, help="Display universal Google Maps navigation deep link")
def plan_trip_cli(
    origin: str,
    stores: tuple[int, ...],
    round_trip: bool,
    optimize: bool,
    mode: str,
    export_gpx: Optional[str],
    export_csv: Optional[str],
    show_url: bool,
) -> None:
    """Plan an optimized multi-stop trip visiting 2 to 12 stores with TSP sequencing."""
    if len(stores) < 2:
        console.print("[red]Error:[/red] Trip planning requires at least 2 store destinations (-s <id> -s <id>).")
        raise click.Abort()

    console.print(f"[cyan]Calculating multi-stop itinerary for {len(stores)} stores from '{origin}'...[/cyan]")

    planner = TripPlannerService()
    req = TripPlanRequest(
        origin=origin,
        store_ids=list(stores),
        round_trip=round_trip,
        optimize=optimize,
        travel_mode=TravelMode(mode),
    )

    try:
        result = asyncio.run(planner.plan_trip(req))
    except ValueError as err:
        console.print(f"[red]Planning Error:[/red] {err}")
        raise click.Abort()

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Multi-Stop Itinerary ({result.travel_mode.value.title()})[/bold cyan]\n"
            f"[bold]Origin:[/bold] {result.origin_label}\n"
            f"[bold]Destination:[/bold] {result.destination_label}\n"
            f"[bold]Stops:[/bold] {len(result.stops)} total ({len(result.legs)} legs) | [bold]Round-Trip:[/bold] {'Yes' if result.round_trip else 'No'}\n"
            f"[bold]Total Distance:[/bold] {result.total_distance_miles:.1f} mi ({result.total_distance_km:.1f} km)\n"
            f"[bold]Total Travel Time:[/bold] {result.total_duration_text}",
            title="Optimized Trip Overview",
            border_style="cyan",
        )
    )

    # Optimization savings panel if available
    if result.savings:
        console.print(
            Panel(
                f"[bold green]TSP Optimization Saved:[/bold green] [bold]{result.savings.distance_saved_miles:.1f} miles[/bold] "
                f"({result.savings.percentage_distance_saved:.1f}% distance reduction)\n"
                f"[bold]Naive Distance:[/bold] {result.savings.naive_distance_km * 0.621371:.1f} mi -> [bold]Optimized Distance:[/bold] {result.savings.optimized_distance_km * 0.621371:.1f} mi\n"
                f"[bold]Estimated Drive Time Saved:[/bold] ~{result.savings.estimated_minutes_saved:.0f} mins",
                title="Route Efficiency Savings",
                border_style="green",
            )
        )

    # Sequential Stops Table
    stops_table = Table(title="Sequential Stop Schedule", show_header=True, header_style="bold magenta")
    stops_table.add_column("Seq", width=4, justify="right")
    stops_table.add_column("Role", width=12)
    stops_table.add_column("Location / Store Name", style="bold")
    stops_table.add_column("Address / City")

    for s in result.stops:
        role = "[blue]Origin[/blue]" if s.is_origin else "[green]Return[/green]" if s.is_destination and s.is_origin == False and s.store_id is None else f"Store #{s.store_id}"
        stops_table.add_row(str(s.sequence_index + 1), role, s.name, s.address)

    console.print(stops_table)

    # Leg by Leg Table
    legs_table = Table(title="Leg-by-Leg Route Segments", show_header=True, header_style="bold blue")
    legs_table.add_column("Leg", width=4, justify="right")
    legs_table.add_column("From", style="cyan")
    legs_table.add_column("To", style="green")
    legs_table.add_column("Distance", width=12, justify="right")
    legs_table.add_column("Duration", width=12, justify="right")

    for leg in result.legs:
        legs_table.add_row(
            str(leg.leg_index + 1),
            leg.start_node.name[:25],
            leg.end_node.name[:25],
            leg.distance_text,
            leg.duration_text,
        )

    console.print(legs_table)

    if show_url and result.google_maps_url:
        console.print(
            Panel(
                f"[bold underline cyan]{result.google_maps_url}[/bold underline cyan]",
                title="Universal Google Maps Mobile Navigation URL",
                border_style="blue",
            )
        )

    if export_gpx:
        gpx_data = TripExporter.generate_gpx(result)
        with open(export_gpx, "w", encoding="utf-8") as f:
            f.write(gpx_data)
        console.print(f"[bold green]Exported GPX 1.1 route file:[/bold green] {export_gpx}")

    if export_csv:
        csv_data = TripExporter.generate_csv(result)
        with open(export_csv, "w", encoding="utf-8") as f:
            f.write(csv_data)
        console.print(f"[bold green]Exported Driver CSV manifest:[/bold green] {export_csv}")

    console.print(f"\n[dim]Overview Polyline ({len(result.overview_polyline)} chars):[/dim] [italic]{result.overview_polyline[:40]}...[/italic]\n")


@cli.command()
@click.option("--host", default=settings.host, show_default=True, help="Host to bind server")
@click.option("--port", default=settings.port, show_default=True, help="Port to bind server")
def serve(host: str, port: int) -> None:
    """Launch the FastAPI server and interactive web UI."""
    import uvicorn
    console.print(f"[bold green]Starting Store Locator server at http://{host}:{port}[/bold green]")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    cli()
