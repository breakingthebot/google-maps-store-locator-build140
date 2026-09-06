# src/services/store_repository.py
# SQLite persistence layer for store locations, geospatial proximity filtering, and default store seeds.
# Connects to: src/config.py, src/models/store.py, src/utils/distance.py, src/utils/hours.py
# Created: 2026-09-06

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional
from src.config import settings
from src.models.store import (
    DayHours,
    Store,
    StoreAmenities,
    StoreCreate,
    StoreReview,
    StoreSummary,
    WeeklyHours,
)
from src.utils.distance import (
    calculate_bounding_box,
    haversine_distance_km,
    haversine_distance_miles,
)
from src.utils.hours import is_store_open

logger = logging.getLogger("store_locator.repository")


class StoreRepository:
    """Thread-safe SQLite repository managing store records, amenities, and spatial queries."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db_path = Path(db_path or settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a new connection with Row row_factory for dict-like column access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize_db(self) -> None:
        """Create database tables and geospatial indexes if they do not exist."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    brand TEXT NOT NULL DEFAULT 'Apex Retail',
                    street TEXT NOT NULL,
                    city TEXT NOT NULL,
                    state TEXT NOT NULL,
                    postal_code TEXT NOT NULL,
                    country TEXT NOT NULL DEFAULT 'US',
                    phone TEXT DEFAULT '',
                    website TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    rating REAL NOT NULL DEFAULT 4.5,
                    user_ratings_total INTEGER NOT NULL DEFAULT 0,
                    place_id TEXT,
                    amenities_json TEXT NOT NULL DEFAULT '{}',
                    hours_json TEXT NOT NULL DEFAULT '{}',
                    reviews_json TEXT NOT NULL DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stores_lat_lng ON stores(latitude, longitude);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stores_city ON stores(city);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_stores_rating ON stores(rating);")
            conn.commit()

        # Seed data if empty
        self.seed_if_empty()

    def _row_to_store(self, row: sqlite3.Row) -> Store:
        """Deserialize an SQLite row into a validated Store entity."""
        try:
            amenities_data = json.loads(row["amenities_json"] or "{}")
            amenities = StoreAmenities(**amenities_data)
        except Exception:
            amenities = StoreAmenities()

        try:
            hours_data = json.loads(row["hours_json"] or "{}")
            hours = WeeklyHours(**hours_data)
        except Exception:
            hours = WeeklyHours()

        try:
            reviews_data = json.loads(row["reviews_json"] or "[]")
            reviews = [StoreReview(**r) for r in reviews_data]
        except Exception:
            reviews = []

        return Store(
            id=row["id"],
            name=row["name"],
            brand=row["brand"],
            street=row["street"],
            city=row["city"],
            state=row["state"],
            postal_code=row["postal_code"],
            country=row["country"],
            phone=row["phone"] or "",
            website=row["website"] or "",
            email=row["email"] or "",
            latitude=row["latitude"],
            longitude=row["longitude"],
            rating=row["rating"],
            user_ratings_total=row["user_ratings_total"],
            place_id=row["place_id"],
            amenities=amenities,
            hours=hours,
            reviews=reviews,
        )

    def get_by_id(self, store_id: int) -> Optional[Store]:
        """Fetch a single store by its unique integer ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM stores WHERE id = ?", (store_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_store(row)
            return None

    def add_store(self, store_data: StoreCreate) -> Store:
        """Insert a new store record and return the persistent Store instance."""
        amenities_json = json.dumps(store_data.amenities.model_dump())
        hours_json = json.dumps(store_data.hours.model_dump())
        reviews_json = json.dumps([])

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO stores (
                    name, brand, street, city, state, postal_code, country,
                    phone, website, email, latitude, longitude,
                    rating, user_ratings_total, place_id,
                    amenities_json, hours_json, reviews_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    store_data.name,
                    store_data.brand,
                    store_data.street,
                    store_data.city,
                    store_data.state,
                    store_data.postal_code,
                    store_data.country,
                    store_data.phone,
                    store_data.website,
                    store_data.email,
                    store_data.latitude,
                    store_data.longitude,
                    4.5,
                    1,
                    f"place_{int(store_data.latitude * 1000)}_{int(store_data.longitude * 1000)}",
                    amenities_json,
                    hours_json,
                    reviews_json,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid

        created = self.get_by_id(new_id)
        if not created:
            raise RuntimeError(f"Failed to retrieve store {new_id} after insert")
        return created

    def list_all(self, limit: int = 100) -> list[Store]:
        """List stores up to the requested limit."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM stores ORDER BY id ASC LIMIT ?", (limit,))
            return [self._row_to_store(r) for r in cursor.fetchall()]

    def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 25.0,
        open_now: bool = False,
        min_rating: Optional[float] = None,
        amenity: Optional[str] = None,
        amenities_filter: Optional[dict[str, bool]] = None,
        sort_by: str = "distance",
        limit: int = 50,
    ) -> list[StoreSummary]:
        """Geospatially search for stores within a given radius using bounding box pre-filtering.

        Calculates exact Haversine distance, applies real-time operating hours check,
        and filters by amenities and rating.
        """
        bbox = calculate_bounding_box(latitude, longitude, radius_km)

        # Pre-filter using indexed bounding box coordinates
        query = """
            SELECT * FROM stores
            WHERE latitude >= ? AND latitude <= ?
              AND longitude >= ? AND longitude <= ?
        """
        params: list = [
            bbox.min_latitude,
            bbox.max_latitude,
            bbox.min_longitude,
            bbox.max_longitude,
        ]

        if min_rating is not None and min_rating > 0:
            query += " AND rating >= ?"
            params.append(min_rating)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

        summaries: list[StoreSummary] = []

        for row in rows:
            store = self._row_to_store(row)

            # Check single amenity filter if requested (legacy compatibility)
            if amenity:
                clean_amenity = amenity.strip().lower()
                amenities_dict = store.amenities.model_dump()
                if not amenities_dict.get(clean_amenity, False):
                    continue

            # Check multiple amenity filters if requested (e.g. drive_thru, wifi, ev_charging)
            if amenities_filter:
                amenities_dict = store.amenities.model_dump()
                mismatch = False
                for req_key, req_val in amenities_filter.items():
                    if req_val and not amenities_dict.get(req_key, False):
                        mismatch = True
                        break
                if mismatch:
                    continue

            # Calculate exact Haversine distance
            dist_km = haversine_distance_km(latitude, longitude, store.latitude, store.longitude)
            if dist_km > radius_km:
                continue

            dist_miles = haversine_distance_miles(latitude, longitude, store.latitude, store.longitude)

            # Evaluate real-time operating hours
            is_open, status_text, closing_soon = is_store_open(store.hours)

            if open_now and not is_open:
                continue

            summaries.append(
                StoreSummary(
                    store=store,
                    distance_km=dist_km,
                    distance_miles=dist_miles,
                    is_open_now=is_open,
                    status_text=status_text,
                    closing_soon=closing_soon,
                )
            )

        # Sorting logic
        if sort_by == "rating":
            summaries.sort(key=lambda s: (-s.store.rating, s.distance_km))
        elif sort_by == "name":
            summaries.sort(key=lambda s: s.store.name.lower())
        else:  # default "distance"
            summaries.sort(key=lambda s: s.distance_km)

        return summaries[:limit]

    def seed_if_empty(self) -> None:
        """Populate database with 20 realistic store locations if currently empty."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM stores;")
            if cursor.fetchone()["cnt"] > 0:
                return

        logger.info("Database empty. Seeding flagship retail locations across metropolitan hubs.")
        seed_stores = [
            # San Francisco Bay Area (Primary cluster)
            {
                "name": "Apex Retail - Union Square Flagship",
                "brand": "Apex Retail",
                "street": "170 Geary St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94108",
                "country": "US",
                "phone": "+1 (415) 555-0101",
                "website": "https://apexretail.example.com/stores/union-square",
                "email": "unionsquare@apexretail.example.com",
                "latitude": 37.787834,
                "longitude": -122.406127,
                "rating": 4.9,
                "user_ratings_total": 428,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Marcus Vance", "rating": 5.0, "text": "Exceptional service and instant curbside pickup. Great central location!", "relative_time_description": "2 days ago"},
                    {"author_name": "Elena Rostova", "rating": 4.8, "text": "Super clean store with helpful staff. Fast WiFi inside.", "relative_time_description": "1 week ago"}
                ]
            },
            {
                "name": "Apex Retail - Mission District Hub",
                "brand": "Apex Retail",
                "street": "2450 Mission St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94110",
                "country": "US",
                "phone": "+1 (415) 555-0102",
                "website": "https://apexretail.example.com/stores/mission",
                "email": "mission@apexretail.example.com",
                "latitude": 37.759240,
                "longitude": -122.419120,
                "rating": 4.7,
                "user_ratings_total": 312,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "tuesday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "wednesday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "thursday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "friday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "sunday": {"open_time": "12:30", "close_time": "18:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Sophia Chen", "rating": 5.0, "text": "Vibrant neighborhood atmosphere and wonderful inventory selection.", "relative_time_description": "3 days ago"}
                ]
            },
            {
                "name": "Apex Retail - SoMa Tech Center",
                "brand": "Apex Retail",
                "street": "850 Folsom St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94107",
                "country": "US",
                "phone": "+1 (415) 555-0103",
                "website": "https://apexretail.example.com/stores/soma",
                "email": "soma@apexretail.example.com",
                "latitude": 37.781210,
                "longitude": -122.403450,
                "rating": 4.6,
                "user_ratings_total": 289,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "07:30", "close_time": "21:30", "is_closed": False},
                    "tuesday": {"open_time": "07:30", "close_time": "21:30", "is_closed": False},
                    "wednesday": {"open_time": "07:30", "close_time": "21:30", "is_closed": False},
                    "thursday": {"open_time": "07:30", "close_time": "21:30", "is_closed": False},
                    "friday": {"open_time": "07:30", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "08:30", "close_time": "21:00", "is_closed": False},
                    "sunday": {"open_time": "09:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Devin Wright", "rating": 4.5, "text": "Quick pickup right before work. EV chargers worked without a hitch.", "relative_time_description": "5 days ago"}
                ]
            },
            {
                "name": "Apex Retail - Marina Promenade",
                "brand": "Apex Retail",
                "street": "2120 Chestnut St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94123",
                "country": "US",
                "phone": "+1 (415) 555-0104",
                "website": "https://apexretail.example.com/stores/marina",
                "email": "marina@apexretail.example.com",
                "latitude": 37.799820,
                "longitude": -122.438910,
                "rating": 4.8,
                "user_ratings_total": 514,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "20:30", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "20:30", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "20:30", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "20:30", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "21:30", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "21:30", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "18:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Claire Dupont", "rating": 5.0, "text": "Delightful shopping trip! The curbside pickup was ready in 5 minutes.", "relative_time_description": "1 week ago"}
                ]
            },
            {
                "name": "Apex Retail - Fisherman's Wharf Plaza",
                "brand": "Apex Retail",
                "street": "300 Beach St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94133",
                "country": "US",
                "phone": "+1 (415) 555-0105",
                "website": "https://apexretail.example.com/stores/wharf",
                "email": "wharf@apexretail.example.com",
                "latitude": 37.807500,
                "longitude": -122.416200,
                "rating": 4.5,
                "user_ratings_total": 620,
                "amenities": {"drive_thru": True, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "23:00", "is_closed": False},
                    "saturday": {"open_time": "08:00", "close_time": "23:00", "is_closed": False},
                    "sunday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Liam Gallagher", "rating": 4.5, "text": "Rare drive-thru in the city! Extremely convenient.", "relative_time_description": "4 days ago"}
                ]
            },
            {
                "name": "Apex Retail - Sunset Boulevard",
                "brand": "Apex Retail",
                "street": "1940 Irving St",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94122",
                "country": "US",
                "phone": "+1 (415) 555-0106",
                "website": "https://apexretail.example.com/stores/sunset",
                "email": "sunset@apexretail.example.com",
                "latitude": 37.763520,
                "longitude": -122.478910,
                "rating": 4.4,
                "user_ratings_total": 195,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:30", "close_time": "20:00", "is_closed": False},
                    "tuesday": {"open_time": "08:30", "close_time": "20:00", "is_closed": False},
                    "wednesday": {"open_time": "08:30", "close_time": "20:00", "is_closed": False},
                    "thursday": {"open_time": "08:30", "close_time": "20:00", "is_closed": False},
                    "friday": {"open_time": "08:30", "close_time": "21:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "18:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Rachel Kim", "rating": 4.0, "text": "Quiet neighborhood location with easy street parking.", "relative_time_description": "2 weeks ago"}
                ]
            },
            {
                "name": "Apex Retail - Oakland Uptown",
                "brand": "Apex Retail",
                "street": "2100 Broadway",
                "city": "Oakland",
                "state": "CA",
                "postal_code": "94612",
                "country": "US",
                "phone": "+1 (510) 555-0107",
                "website": "https://apexretail.example.com/stores/oakland",
                "email": "oakland@apexretail.example.com",
                "latitude": 37.810560,
                "longitude": -122.268920,
                "rating": 4.7,
                "user_ratings_total": 340,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Tariq Washington", "rating": 5.0, "text": "Right near 19th St BART. Super fast in-and-out experience.", "relative_time_description": "3 days ago"}
                ]
            },
            {
                "name": "Apex Retail - Berkeley Campus",
                "brand": "Apex Retail",
                "street": "2290 Shattuck Ave",
                "city": "Berkeley",
                "state": "CA",
                "postal_code": "94704",
                "country": "US",
                "phone": "+1 (510) 555-0108",
                "website": "https://apexretail.example.com/stores/berkeley",
                "email": "berkeley@apexretail.example.com",
                "latitude": 37.868840,
                "longitude": -122.268150,
                "rating": 4.6,
                "user_ratings_total": 412,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Jessica Lee", "rating": 4.8, "text": "Student friendly, well stocked with electronics and everyday goods.", "relative_time_description": "5 days ago"}
                ]
            },
            {
                "name": "Apex Retail - Silicon Valley Supercenter",
                "brand": "Apex Retail",
                "street": "3000 El Camino Real",
                "city": "Palo Alto",
                "state": "CA",
                "postal_code": "94306",
                "country": "US",
                "phone": "+1 (650) 555-0109",
                "website": "https://apexretail.example.com/stores/palo-alto",
                "email": "paloalto@apexretail.example.com",
                "latitude": 37.424100,
                "longitude": -122.143200,
                "rating": 4.9,
                "user_ratings_total": 850,
                "amenities": {"drive_thru": True, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "07:00", "close_time": "23:00", "is_closed": False},
                    "tuesday": {"open_time": "07:00", "close_time": "23:00", "is_closed": False},
                    "wednesday": {"open_time": "07:00", "close_time": "23:00", "is_closed": False},
                    "thursday": {"open_time": "07:00", "close_time": "23:00", "is_closed": False},
                    "friday": {"open_time": "07:00", "close_time": "23:00", "is_closed": False},
                    "saturday": {"open_time": "08:00", "close_time": "23:00", "is_closed": False},
                    "sunday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Arjun Patel", "rating": 5.0, "text": "Huge parking lot, 12 Level 3 EV chargers, and great customer service.", "relative_time_description": "yesterday"}
                ]
            },
            # New York City Cluster
            {
                "name": "Apex Retail - Manhattan Fifth Ave",
                "brand": "Apex Retail",
                "street": "650 5th Ave",
                "city": "New York",
                "state": "NY",
                "postal_code": "10019",
                "country": "US",
                "phone": "+1 (212) 555-0201",
                "website": "https://apexretail.example.com/stores/5th-ave",
                "email": "manhattan@apexretail.example.com",
                "latitude": 40.759840,
                "longitude": -73.977410,
                "rating": 4.9,
                "user_ratings_total": 1250,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Samantha Jones", "rating": 5.0, "text": "Prime Manhattan flagship. Impeccable architecture and staff.", "relative_time_description": "3 days ago"}
                ]
            },
            {
                "name": "Apex Retail - SoHo Boutique",
                "brand": "Apex Retail",
                "street": "110 Prince St",
                "city": "New York",
                "state": "NY",
                "postal_code": "10012",
                "country": "US",
                "phone": "+1 (212) 555-0202",
                "website": "https://apexretail.example.com/stores/soho",
                "email": "soho@apexretail.example.com",
                "latitude": 40.724810,
                "longitude": -74.000120,
                "rating": 4.7,
                "user_ratings_total": 498,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                    "tuesday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                    "wednesday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                    "thursday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                    "friday": {"open_time": "10:00", "close_time": "21:00", "is_closed": False},
                    "saturday": {"open_time": "10:00", "close_time": "21:00", "is_closed": False},
                    "sunday": {"open_time": "11:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Oliver Twist", "rating": 4.5, "text": "Beautiful cobblestone street, curated catalog.", "relative_time_description": "1 week ago"}
                ]
            },
            # Seattle Cluster
            {
                "name": "Apex Retail - Downtown Seattle",
                "brand": "Apex Retail",
                "street": "500 Pine St",
                "city": "Seattle",
                "state": "WA",
                "postal_code": "98101",
                "country": "US",
                "phone": "+1 (206) 555-0301",
                "website": "https://apexretail.example.com/stores/seattle-downtown",
                "email": "seattle@apexretail.example.com",
                "latitude": 47.611910,
                "longitude": -122.336420,
                "rating": 4.8,
                "user_ratings_total": 560,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "18:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Lucas Grey", "rating": 5.0, "text": "Right near Westlake transit mall. Seamless checkout!", "relative_time_description": "4 days ago"}
                ]
            },
            # Chicago Cluster
            {
                "name": "Apex Retail - Chicago Michigan Ave",
                "brand": "Apex Retail",
                "street": "401 N Michigan Ave",
                "city": "Chicago",
                "state": "IL",
                "postal_code": "60611",
                "country": "US",
                "phone": "+1 (312) 555-0401",
                "website": "https://apexretail.example.com/stores/chicago",
                "email": "chicago@apexretail.example.com",
                "latitude": 41.890120,
                "longitude": -87.624190,
                "rating": 4.8,
                "user_ratings_total": 780,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "19:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Maya Lin", "rating": 4.9, "text": "Stunning location along the Chicago Riverwalk!", "relative_time_description": "2 days ago"}
                ]
            },
            # Austin Cluster
            {
                "name": "Apex Retail - Austin South Congress",
                "brand": "Apex Retail",
                "street": "1401 S Congress Ave",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78704",
                "country": "US",
                "phone": "+1 (512) 555-0501",
                "website": "https://apexretail.example.com/stores/austin",
                "email": "austin@apexretail.example.com",
                "latitude": 30.251410,
                "longitude": -97.749120,
                "rating": 4.9,
                "user_ratings_total": 490,
                "amenities": {"drive_thru": True, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "08:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "08:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Austin Hunter", "rating": 5.0, "text": "Love the drive-thru and EV chargers on SoCo. Fast and polite!", "relative_time_description": "1 day ago"}
                ]
            },
            # Los Angeles Cluster
            {
                "name": "Apex Retail - Santa Monica Third St",
                "brand": "Apex Retail",
                "street": "1415 3rd Street Promenade",
                "city": "Santa Monica",
                "state": "CA",
                "postal_code": "90401",
                "country": "US",
                "phone": "+1 (310) 555-0601",
                "website": "https://apexretail.example.com/stores/santa-monica",
                "email": "santamonica@apexretail.example.com",
                "latitude": 34.015240,
                "longitude": -118.496120,
                "rating": 4.8,
                "user_ratings_total": 640,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": True, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "tuesday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "wednesday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "thursday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "friday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "22:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "20:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Zoe Saldana", "rating": 5.0, "text": "Beach breezes and great tech retail. Highly recommended.", "relative_time_description": "4 days ago"}
                ]
            },
            # Denver Cluster
            {
                "name": "Apex Retail - Denver 16th Street Mall",
                "brand": "Apex Retail",
                "street": "500 16th St Mall",
                "city": "Denver",
                "state": "CO",
                "postal_code": "80202",
                "country": "US",
                "phone": "+1 (303) 555-0701",
                "website": "https://apexretail.example.com/stores/denver",
                "email": "denver@apexretail.example.com",
                "latitude": 39.743120,
                "longitude": -104.989210,
                "rating": 4.7,
                "user_ratings_total": 310,
                "amenities": {"drive_thru": False, "curbside_pickup": True, "ev_charging": False, "wheelchair_accessible": True, "wifi": True, "in_store_shopping": True},
                "hours": {
                    "monday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "tuesday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "wednesday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "thursday": {"open_time": "09:00", "close_time": "20:00", "is_closed": False},
                    "friday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "saturday": {"open_time": "09:00", "close_time": "21:00", "is_closed": False},
                    "sunday": {"open_time": "10:00", "close_time": "18:00", "is_closed": False},
                },
                "reviews": [
                    {"author_name": "Brett Collins", "rating": 4.7, "text": "Clean and organized store right in downtown Denver.", "relative_time_description": "1 week ago"}
                ]
            },
        ]

        with self._get_connection() as conn:
            for s in seed_stores:
                conn.execute(
                    """
                    INSERT INTO stores (
                        name, brand, street, city, state, postal_code, country,
                        phone, website, email, latitude, longitude,
                        rating, user_ratings_total, place_id,
                        amenities_json, hours_json, reviews_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s["name"],
                        s["brand"],
                        s["street"],
                        s["city"],
                        s["state"],
                        s["postal_code"],
                        s["country"],
                        s["phone"],
                        s["website"],
                        s["email"],
                        s["latitude"],
                        s["longitude"],
                        s["rating"],
                        s["user_ratings_total"],
                        f"seed_place_{int(s['latitude']*100)}_{int(s['longitude']*100)}",
                        json.dumps(s["amenities"]),
                        json.dumps(s["hours"]),
                        json.dumps(s["reviews"]),
                    ),
                )
            conn.commit()
            logger.info("Successfully seeded %d flagship stores.", len(seed_stores))
