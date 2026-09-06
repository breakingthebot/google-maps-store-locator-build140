// src/static/app.js - Frontend application controller and interactive map renderer
// Connects to: /api/stores, /api/directions, /api/geocode, /api/health

(function () {
  'use strict';

  // Application State
  const state = {
    stores: [],
    origin: { lat: 37.774929, lng: -122.419416, name: "San Francisco, CA" },
    selectedStoreId: null,
    activeDirections: null,
    currentTravelMode: "driving",
    radiusKm: 25,
    sortBy: "distance",
    filters: {
      open_now: false,
      rating_45: false,
      drive_thru: false,
      curbside_pickup: false,
      ev_charging: false,
      wheelchair_accessible: false,
      wifi: false,
    },
    googleMapInstance: null,
    googleMarkers: [],
    googleDirectionsRenderer: null,
    svgMapScale: 1.0,
  };

  // DOM Elements
  const searchInput = document.getElementById("search-input");
  const btnSearch = document.getElementById("btn-search");
  const btnLocateMe = document.getElementById("btn-locate-me");
  const providerBadge = document.getElementById("provider-badge");
  const providerName = document.getElementById("provider-name");
  const resultsCount = document.getElementById("results-count");
  const resultsOrigin = document.getElementById("results-origin");
  const storeList = document.getElementById("store-list");
  const mapTarget = document.getElementById("map-target");
  const radiusSelect = document.getElementById("radius-select");
  const sortSelect = document.getElementById("sort-select");
  const directionsDrawer = document.getElementById("directions-drawer");
  const btnCloseDirections = document.getElementById("btn-close-directions");
  const directionsDistance = document.getElementById("directions-distance");
  const directionsDuration = document.getElementById("directions-duration");
  const directionsSteps = document.getElementById("directions-steps");
  const directionsModeTitle = document.getElementById("directions-mode-title");
  const storeModal = document.getElementById("store-modal");
  const btnCloseModal = document.getElementById("btn-close-modal");

  // Initialize
  async function init() {
    setupEventListeners();
    await checkHealthAndConfig();
    await performSearch();
  }

  // Check backend provider status and API config
  async function checkHealthAndConfig() {
    try {
      const res = await fetch("/api/health");
      if (res.ok) {
        const data = await res.json();
        providerName.textContent = data.maps_provider;
        const dot = document.getElementById("provider-dot");
        if (data.live_maps_enabled) {
          dot.style.background = "#2563eb";
          providerBadge.title = "Connected to Live Google Maps Platform";
        } else {
          dot.style.background = "#10b981";
          providerBadge.title = "Operating via High-Fidelity Mock Maps Engine (Offline Ready)";
        }
      }
    } catch (err) {
      console.warn("Failed to check provider health:", err);
      providerName.textContent = "Offline Mode";
    }
  }

  // Setup Event Listeners
  function setupEventListeners() {
    btnSearch.addEventListener("click", () => handleSearchInput());
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSearchInput();
    });

    btnLocateMe.addEventListener("click", handleLocateMe);

    radiusSelect.addEventListener("change", (e) => {
      state.radiusKm = parseFloat(e.target.value);
      performSearch();
    });

    sortSelect.addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      performSearch();
    });

    // Filter Chips
    document.querySelectorAll(".filter-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const filterKey = chip.getAttribute("data-filter");
        chip.classList.toggle("active");
        state.filters[filterKey] = chip.classList.contains("active");
        performSearch();
      });
    });

    btnCloseDirections.addEventListener("click", () => {
      directionsDrawer.classList.remove("open");
      state.activeDirections = null;
      renderMap();
    });

    // Travel mode switcher in directions drawer
    document.querySelectorAll("[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-mode");
        state.currentTravelMode = mode;
        if (state.selectedStoreId) {
          fetchDirections(state.selectedStoreId, mode);
        }
      });
    });

    btnCloseModal.addEventListener("click", () => {
      storeModal.classList.remove("open");
    });

    storeModal.addEventListener("click", (e) => {
      if (e.target === storeModal) {
        storeModal.classList.remove("open");
      }
    });

    document.getElementById("modal-btn-directions").addEventListener("click", () => {
      storeModal.classList.remove("open");
      if (state.selectedStoreId) {
        fetchDirections(state.selectedStoreId, state.currentTravelMode);
      }
    });
  }

  // Perform Store Search
  async function performSearch() {
    storeList.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--text-muted);">Finding nearest locations...</div>`;

    const params = new URLSearchParams({
      lat: state.origin.lat,
      lng: state.origin.lng,
      radius_km: state.radiusKm,
      sort_by: state.sortBy,
      open_now: state.filters.open_now,
    });

    if (state.filters.rating_45) {
      params.append("min_rating", "4.5");
    }

    // Amenity filters
    const amenityKeys = ["drive_thru", "curbside_pickup", "ev_charging", "wheelchair_accessible", "wifi"];
    for (const k of amenityKeys) {
      if (state.filters[k]) {
        params.append("amenity", k);
        break; // API handles single amenity filter parameter per query
      }
    }

    try {
      const res = await fetch(`/api/stores?${params.toString()}`);
      if (!res.ok) throw new Error("Search request failed");
      const data = await res.json();

      state.stores = data.stores;
      resultsCount.textContent = `${data.total_found} locations found`;
      resultsOrigin.textContent = `near ${data.search_address}`;

      renderStoreCards();
      renderMap();
    } catch (err) {
      console.error("Search failed:", err);
      storeList.innerHTML = `<div style="padding: 24px; text-align: center; color: var(--danger);">Failed to load store locations. Please try again.</div>`;
    }
  }

  // Handle Search Input Geocoding
  async function handleSearchInput() {
    const query = searchInput.value.trim();
    if (!query) return;

    try {
      const res = await fetch(`/api/geocode?address=${encodeURIComponent(query)}`);
      if (!res.ok) {
        alert(`Location "${query}" could not be found. Please try another address or city.`);
        return;
      }
      const geo = await res.json();
      state.origin = {
        lat: geo.coordinates.latitude,
        lng: geo.coordinates.longitude,
        name: geo.formatted_address,
      };
      performSearch();
    } catch (err) {
      console.error("Geocoding failed:", err);
    }
  }

  // Handle HTML5 Geolocation
  function handleLocateMe() {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    btnLocateMe.disabled = true;
    btnLocateMe.querySelector("span").textContent = "Locating...";

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        btnLocateMe.disabled = false;
        btnLocateMe.querySelector("span").textContent = "Locate Me";
        state.origin = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          name: "My Current Location",
        };
        performSearch();
      },
      (err) => {
        btnLocateMe.disabled = false;
        btnLocateMe.querySelector("span").textContent = "Locate Me";
        console.warn("Geolocation denied or error:", err);
        alert("Unable to retrieve GPS coordinates. Defaulting to San Francisco.");
      },
      { timeout: 8000 }
    );
  }

  // Render Sidebar Store Cards
  function renderStoreCards() {
    if (!state.stores || state.stores.length === 0) {
      storeList.innerHTML = `
        <div style="padding: 40px 20px; text-align: center;">
          <div style="font-size: 2.5rem; margin-bottom: 12px;">🏪</div>
          <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 6px;">No stores found</h3>
          <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">
            No stores match your search within ${state.radiusKm} km. Try expanding your search radius or clearing filter chips.
          </p>
        </div>
      `;
      return;
    }

    storeList.innerHTML = "";
    state.stores.forEach((item, index) => {
      const store = item.store;
      const isSelected = store.id === state.selectedStoreId;

      const card = document.createElement("div");
      card.className = `store-card ${isSelected ? "selected" : ""}`;
      card.id = `store-card-${store.id}`;

      const statusClass = item.is_open_now ? "status-open" : "status-closed";
      const statusIcon = item.is_open_now ? "●" : "○";

      const tags = [];
      if (store.amenities.drive_thru) tags.push("Drive-Thru");
      if (store.amenities.curbside_pickup) tags.push("Curbside");
      if (store.amenities.ev_charging) tags.push("EV Fast Charging");
      if (store.amenities.wifi) tags.push("Free WiFi");

      card.innerHTML = `
        <div class="store-card-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; background: var(--primary); color: white; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: bold;">
              ${index + 1}
            </div>
            <div class="store-title">${escapeHtml(store.name)}</div>
          </div>
          <span class="distance-badge">${item.distance_miles.toFixed(1)} mi</span>
        </div>
        <div class="store-address">${escapeHtml(store.street)}, ${escapeHtml(store.city)}, ${escapeHtml(store.state)} ${escapeHtml(store.postal_code)}</div>
        <div class="store-meta-row">
          <span class="status-pill ${statusClass}">${statusIcon} ${escapeHtml(item.status_text)}</span>
          <span class="rating-badge">★ ${store.rating.toFixed(1)} <span style="font-weight: normal; color: var(--text-muted);">(${store.user_ratings_total})</span></span>
        </div>
        <div class="amenity-tags">
          ${tags.map((t) => `<span class="amenity-tag">${t}</span>`).join("")}
        </div>
        <div class="card-actions">
          <button class="btn-card primary" data-action="directions" data-id="${store.id}">Directions</button>
          <button class="btn-card" data-action="details" data-id="${store.id}">View Hours</button>
          ${store.phone ? `<a href="tel:${escapeHtml(store.phone)}" class="btn-card" style="text-decoration: none;" title="Call Store">📞 Call</a>` : ""}
        </div>
      `;

      // Card click selection
      card.addEventListener("click", (e) => {
        if (e.target.closest("button") || e.target.closest("a")) return;
        selectStore(store.id);
      });

      // Action buttons
      card.querySelector('[data-action="directions"]').addEventListener("click", (e) => {
        e.stopPropagation();
        selectStore(store.id);
        fetchDirections(store.id, state.currentTravelMode);
      });

      card.querySelector('[data-action="details"]').addEventListener("click", (e) => {
        e.stopPropagation();
        openStoreModal(store);
      });

      storeList.appendChild(card);
    });
  }

  // Select Store Card and highlight on map
  function selectStore(storeId) {
    state.selectedStoreId = storeId;
    document.querySelectorAll(".store-card").forEach((c) => c.classList.remove("selected"));
    const activeCard = document.getElementById(`store-card-${storeId}`);
    if (activeCard) {
      activeCard.classList.add("selected");
      activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
    renderMap();
  }

  // Fetch Directions
  async function fetchDirections(storeId, mode) {
    state.selectedStoreId = storeId;
    directionsDrawer.classList.add("open");
    directionsSteps.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted);">Calculating turn-by-turn route...</div>`;

    try {
      const url = `/api/directions?origin_lat=${state.origin.lat}&origin_lng=${state.origin.lng}&destination_store_id=${storeId}&mode=${mode}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Directions request failed");
      const result = await res.json();

      state.activeDirections = result;
      directionsDistance.textContent = result.distance_text;
      directionsDuration.textContent = `Estimated duration: ${result.duration_text}`;
      directionsModeTitle.textContent = `${mode.charAt(0).toUpperCase() + mode.slice(1)} Route`;

      // Render Steps
      directionsSteps.innerHTML = "";
      result.steps.forEach((step, idx) => {
        const stepEl = document.createElement("div");
        stepEl.className = "step-item";
        stepEl.innerHTML = `
          <div class="step-number">${idx + 1}</div>
          <div style="flex: 1;">
            <div style="font-weight: 600; margin-bottom: 2px;">${escapeHtml(step.instruction)}</div>
            <div style="color: var(--text-muted); font-size: 0.78rem;">${step.distance_text} · ${step.duration_text}</div>
          </div>
        `;
        directionsSteps.appendChild(stepEl);
      });

      renderMap();
    } catch (err) {
      console.error("Directions error:", err);
      directionsSteps.innerHTML = `<div style="padding: 16px; color: var(--danger);">Failed to calculate route.</div>`;
    }
  }

  // Open Detailed Store Modal
  function openStoreModal(store) {
    state.selectedStoreId = store.id;
    document.getElementById("modal-store-name").textContent = store.name;
    document.getElementById("modal-store-brand").textContent = `${store.brand} · ${store.city}`;
    document.getElementById("modal-store-address").textContent = store.full_address;
    document.getElementById("modal-store-phone").textContent = store.phone ? `Phone: ${store.phone}` : "";

    // Hours
    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    const todayIndex = (new Date().getDay() + 6) % 7; // Monday = 0
    const tbody = document.getElementById("modal-hours-body");
    tbody.innerHTML = "";

    days.forEach((day, idx) => {
      const dayHours = store.hours[day] || { is_closed: false, open_time: "08:00", close_time: "21:00" };
      const tr = document.createElement("tr");
      if (idx === todayIndex) tr.className = "today";

      const timeDisplay = dayHours.is_closed
        ? `<span style="color: var(--danger); font-weight: 600;">Closed</span>`
        : `${format12(dayHours.open_time)} – ${format12(dayHours.close_time)}`;

      tr.innerHTML = `
        <td style="font-weight: ${idx === todayIndex ? "700" : "500"}; width: 120px;">
          ${day.charAt(0).toUpperCase() + day.slice(1)} ${idx === todayIndex ? '<span style="color: var(--accent); font-size: 0.75rem;">(Today)</span>' : ""}
        </td>
        <td style="text-align: right;">${timeDisplay}</td>
      `;
      tbody.appendChild(tr);
    });

    // Amenities
    const amenitiesContainer = document.getElementById("modal-amenities");
    amenitiesContainer.innerHTML = "";
    const am = store.amenities;
    const items = [
      { key: "drive_thru", label: "Drive-Thru Window", active: am.drive_thru },
      { key: "curbside_pickup", label: "Curbside Pickup", active: am.curbside_pickup },
      { key: "ev_charging", label: "EV Charging Stations", active: am.ev_charging },
      { key: "wheelchair_accessible", label: "Wheelchair Accessible", active: am.wheelchair_accessible },
      { key: "wifi", label: "High-Speed WiFi", active: am.wifi },
      { key: "in_store_shopping", label: "In-Store Shopping", active: am.in_store_shopping },
    ];
    items.forEach((item) => {
      const pill = document.createElement("span");
      pill.className = "amenity-tag";
      pill.style.background = item.active ? "var(--primary-light)" : "var(--surface-secondary)";
      pill.style.color = item.active ? "var(--primary)" : "var(--text-muted)";
      pill.style.fontWeight = item.active ? "600" : "normal";
      pill.textContent = `${item.active ? "✓ " : ""}${item.label}`;
      amenitiesContainer.appendChild(pill);
    });

    // Reviews
    const reviewsContainer = document.getElementById("modal-reviews");
    reviewsContainer.innerHTML = "";
    if (store.reviews && store.reviews.length > 0) {
      store.reviews.forEach((r) => {
        const revCard = document.createElement("div");
        revCard.className = "review-card";
        revCard.innerHTML = `
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="font-weight: 700;">${escapeHtml(r.author_name)}</span>
            <span style="color: #b45309;">★ ${r.rating.toFixed(1)}</span>
          </div>
          <div style="color: var(--text); line-height: 1.4;">"${escapeHtml(r.text)}"</div>
          <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">${escapeHtml(r.relative_time_description)}</div>
        `;
        reviewsContainer.appendChild(revCard);
      });
    } else {
      reviewsContainer.innerHTML = `<div style="font-size: 0.85rem; color: var(--text-muted);">No reviews posted yet.</div>`;
    }

    storeModal.classList.add("open");
  }

  // Render Interactive Map (Dual Engine: Google Maps or High-Fidelity Geospatial SVG Canvas)
  function renderMap() {
    renderGeospatialSvgMap();
  }

  // Geospatial SVG Canvas Map Engine
  function renderGeospatialSvgMap() {
    const stores = state.stores || [];
    const origin = state.origin;

    // Calculate map bounding box
    let minLat = origin.lat;
    let maxLat = origin.lat;
    let minLng = origin.lng;
    let maxLng = origin.lng;

    stores.forEach((s) => {
      const st = s.store;
      if (st.latitude < minLat) minLat = st.latitude;
      if (st.latitude > maxLat) maxLat = st.latitude;
      if (st.longitude < minLng) minLng = st.longitude;
      if (st.longitude > maxLng) maxLng = st.longitude;
    });

    // Add padding margin (at least 0.05 degrees)
    const latSpan = Math.max(0.06, (maxLat - minLat) * 1.3);
    const lngSpan = Math.max(0.08, (maxLng - minLng) * 1.3);
    const centerLat = (minLat + maxLat) / 2;
    const centerLng = (minLng + maxLng) / 2;

    const mapBoxLatMin = centerLat - latSpan / 2;
    const mapBoxLatMax = centerLat + latSpan / 2;
    const mapBoxLngMin = centerLng - lngSpan / 2;
    const mapBoxLngMax = centerLng + lngSpan / 2;

    const width = 800;
    const height = 600;

    function project(lat, lng) {
      const x = ((lng - mapBoxLngMin) / (mapBoxLngMax - mapBoxLngMin)) * width;
      const y = height - ((lat - mapBoxLatMin) / (mapBoxLatMax - mapBoxLatMin)) * height;
      return { x: Math.round(x), y: Math.round(y) };
    }

    const originPt = project(origin.lat, origin.lng);

    // Build Route Polyline Path if directions active
    let polylineSvg = "";
    if (state.activeDirections && state.activeDirections.route_coordinates) {
      const pts = state.activeDirections.route_coordinates.map((c) => {
        const pt = project(c.latitude, c.longitude);
        return `${pt.x},${pt.y}`;
      });
      polylineSvg = `
        <polyline points="${pts.join(" ")}" fill="none" stroke="#2563eb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.9" />
        <polyline points="${pts.join(" ")}" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
      `;
    }

    // Build Store Pin Markers
    let markersSvg = "";
    stores.forEach((item, index) => {
      const st = item.store;
      const pt = project(st.latitude, st.longitude);
      const isSelected = st.id === state.selectedStoreId;
      const pinColor = item.is_open_now ? "#10b981" : "#ef4444";
      const scale = isSelected ? 1.3 : 1.0;

      markersSvg += `
        <g class="map-pin" data-store-id="${st.id}" transform="translate(${pt.x}, ${pt.y}) scale(${scale})" style="cursor: pointer;">
          <circle cx="0" cy="0" r="${isSelected ? 18 : 14}" fill="${pinColor}" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0px 3px 3px rgba(0,0,0,0.25))" />
          <text x="0" y="4" font-size="11" font-weight="bold" fill="#ffffff" text-anchor="middle" font-family="sans-serif">${index + 1}</text>
          ${isSelected ? `<circle cx="0" cy="0" r="22" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-dasharray="3,3" />` : ""}
        </g>
      `;
    });

    // Grid / Map Background Aesthetics
    mapTarget.innerHTML = `
      <div class="svg-map-wrapper">
        <svg id="interactive-svg-map" viewBox="0 0 ${width} ${height}" style="width: 100%; height: 100%; background: #eef2f6;">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#e2e8f0" stroke-width="1"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          <!-- Simulated major street arteries -->
          <line x1="0" y1="${height * 0.45}" x2="${width}" y2="${height * 0.45}" stroke="#ffffff" stroke-width="12" />
          <line x1="0" y1="${height * 0.45}" x2="${width}" y2="${height * 0.45}" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="8,6" />
          <line x1="${width * 0.52}" y1="0" x2="${width * 0.52}" y2="${height}" stroke="#ffffff" stroke-width="10" />
          <line x1="${width * 0.52}" y1="0" x2="${width * 0.52}" y2="${height}" stroke="#cbd5e1" stroke-width="2" stroke-dasharray="8,6" />

          <!-- Active Navigation Polyline -->
          ${polylineSvg}

          <!-- User Origin Radar Pin -->
          <g transform="translate(${originPt.x}, ${originPt.y})">
            <circle cx="0" cy="0" r="18" fill="#3b82f6" opacity="0.25">
              <animate attributeName="r" values="12;24;12" dur="2.5s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.4;0.05;0.4" dur="2.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="0" cy="0" r="7" fill="#2563eb" stroke="#ffffff" stroke-width="2.5"/>
          </g>

          <!-- Store Pins -->
          ${markersSvg}
        </svg>

        <!-- Map Control Overlay -->
        <div class="map-toolbar">
          <button class="map-tool-btn" id="btn-zoom-in" title="Zoom In">+</button>
          <button class="map-tool-btn" id="btn-zoom-out" title="Zoom Out">&minus;</button>
          <button class="map-tool-btn" id="btn-center-origin" title="Center Origin" style="font-size: 0.8rem;">📍</button>
        </div>

        <div style="position: absolute; bottom: 12px; left: 16px; background: rgba(255,255,255,0.9); padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; border: 1px solid var(--border); box-shadow: var(--shadow);">
          <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #10b981; margin-right: 4px;"></span> Open Now
          <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #ef4444; margin: 0 4px 0 10px;"></span> Closed
          <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #2563eb; margin: 0 4px 0 10px;"></span> Your Location
        </div>
      </div>
    `;

    // Add click listeners to SVG store pins
    mapTarget.querySelectorAll(".map-pin").forEach((pin) => {
      pin.addEventListener("click", () => {
        const storeId = parseInt(pin.getAttribute("data-store-id"), 10);
        selectStore(storeId);
      });
    });

    document.getElementById("btn-center-origin").addEventListener("click", () => {
      renderMap();
    });
  }

  // Helpers
  function format12(timeStr) {
    if (!timeStr) return "";
    const parts = timeStr.split(":");
    let h = parseInt(parts[0], 10);
    const m = parts[1];
    const sfx = h >= 12 ? "PM" : "AM";
    h = h % 12 || 12;
    return `${h}:${m} ${sfx}`;
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Kick off application
  window.addEventListener("DOMContentLoaded", init);
})();
