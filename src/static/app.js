// src/static/app.js - Frontend application controller and interactive map renderer
// Connects to: /api/stores, /api/directions, /api/geocode, /api/health, /api/trip/plan
// Created: 2026-09-06

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
    // Multi-Stop Trip Planner State
    tripStoreIds: [],
    activeTripPlan: null,
    googleMapInstance: null,
    googleMarkers: [],
    googleDirectionsRenderer: null,
    svgMapScale: 1.0,
    // Real-Time Traffic Layer & Predictive Departure State
    trafficLayerEnabled: false,
    departureTime: "now",
    trafficModel: "best_guess",
    trafficOverlayData: null,
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

  // Traffic & Departure Elements (Single Route)
  const chipTrafficLayer = document.getElementById("chip-traffic-layer");
  const dirDepartureSelect = document.getElementById("dir-departure-select");
  const dirTrafficModel = document.getElementById("dir-traffic-model");
  const btnDirAdvisor = document.getElementById("btn-dir-advisor");
  const directionsTrafficBadge = document.getElementById("directions-traffic-badge");
  const directionsTrafficText = document.getElementById("directions-traffic-text");
  const directionsTrafficDelay = document.getElementById("directions-traffic-delay");
  const directionsAdvisorBox = document.getElementById("directions-advisor-box");
  const btnCloseDirAdvisor = document.getElementById("btn-close-dir-advisor");
  const dirAdvisorContent = document.getElementById("dir-advisor-content");

  // Trip Planner DOM Elements
  const tripBar = document.getElementById("trip-bar");
  const tripCountBadge = document.getElementById("trip-count-badge");
  const tripStorePills = document.getElementById("trip-store-pills");
  const btnPlanTrip = document.getElementById("btn-plan-trip");
  const btnClearTrip = document.getElementById("btn-clear-trip");
  const tripModal = document.getElementById("trip-modal");
  const btnCloseTripModal = document.getElementById("btn-close-trip-modal");
  const tripRoundTrip = document.getElementById("trip-round-trip");
  const tripOptimize = document.getElementById("trip-optimize");
  const tripDepartureSelect = document.getElementById("trip-departure-select");
  const tripTrafficModel = document.getElementById("trip-traffic-model");
  const tripSavingsBanner = document.getElementById("trip-savings-banner");
  const tripSavingsTitle = document.getElementById("trip-savings-title");
  const tripSavingsDesc = document.getElementById("trip-savings-desc");
  const tripTrafficBanner = document.getElementById("trip-traffic-banner");
  const tripTrafficIcon = document.getElementById("trip-traffic-icon");
  const tripTrafficTitle = document.getElementById("trip-traffic-title");
  const tripTrafficDesc = document.getElementById("trip-traffic-desc");
  const tripTrafficDelayBadge = document.getElementById("trip-traffic-delay-badge");
  const tripStatDistance = document.getElementById("trip-stat-distance");
  const tripStatDuration = document.getElementById("trip-stat-duration");
  const tripStatTrafficSub = document.getElementById("trip-stat-traffic-sub");
  const tripStatStops = document.getElementById("trip-stat-stops");
  const tripStatMode = document.getElementById("trip-stat-mode");
  const tripStopsTimeline = document.getElementById("trip-stops-timeline");
  const tripLegsContainer = document.getElementById("trip-legs-container");
  const tripBtnAdvisor = document.getElementById("trip-btn-advisor");
  const tripAdvisorPopover = document.getElementById("trip-advisor-popover");
  const btnCloseTripAdvisor = document.getElementById("btn-close-trip-advisor");
  const tripAdvisorBars = document.getElementById("trip-advisor-bars");

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
        if (filterKey === "traffic_layer") return; // Handled separately
        state.filters[filterKey] = !state.filters[filterKey];
        chip.classList.toggle("active", state.filters[filterKey]);
        performSearch();
      });
    });

    // Traffic Layer Chip Toggle
    if (chipTrafficLayer) {
      chipTrafficLayer.addEventListener("click", async () => {
        state.trafficLayerEnabled = !state.trafficLayerEnabled;
        chipTrafficLayer.classList.toggle("active", state.trafficLayerEnabled);
        if (state.trafficLayerEnabled && !state.trafficOverlayData) {
          try {
            const res = await fetch("/api/traffic/overlay");
            if (res.ok) {
              const data = await res.json();
              state.trafficOverlayData = data.arterials || [];
            }
          } catch (e) {
            console.warn("Failed to fetch traffic overlay data:", e);
          }
        }
        renderMap();
      });
    }

    // Departure & Traffic Model Selectors (Single Route)
    if (dirDepartureSelect) {
      dirDepartureSelect.addEventListener("change", (e) => {
        state.departureTime = e.target.value;
        if (state.selectedStoreId) {
          fetchDirections(state.selectedStoreId, state.currentTravelMode);
        }
      });
    }

    if (dirTrafficModel) {
      dirTrafficModel.addEventListener("change", (e) => {
        state.trafficModel = e.target.value;
        if (state.selectedStoreId) {
          fetchDirections(state.selectedStoreId, state.currentTravelMode);
        }
      });
    }

    // Departure Advisor (Single Route)
    if (btnDirAdvisor) {
      btnDirAdvisor.addEventListener("click", () => {
        if (!directionsAdvisorBox) return;
        const isHidden = directionsAdvisorBox.classList.contains("hidden");
        if (isHidden) {
          directionsAdvisorBox.classList.remove("hidden");
          fetchDirectionsAdvisor();
        } else {
          directionsAdvisorBox.classList.add("hidden");
        }
      });
    }

    if (btnCloseDirAdvisor) {
      btnCloseDirAdvisor.addEventListener("click", () => {
        if (directionsAdvisorBox) directionsAdvisorBox.classList.add("hidden");
      });
    }

    // Trip Departure & Traffic Selectors
    if (tripDepartureSelect) {
      tripDepartureSelect.addEventListener("change", (e) => {
        state.departureTime = e.target.value;
      });
    }

    if (tripTrafficModel) {
      tripTrafficModel.addEventListener("change", (e) => {
        state.trafficModel = e.target.value;
      });
    }

    // Trip Departure Advisor
    if (tripBtnAdvisor) {
      tripBtnAdvisor.addEventListener("click", () => {
        if (!tripAdvisorPopover) return;
        const isHidden = tripAdvisorPopover.classList.contains("hidden");
        if (isHidden) {
          tripAdvisorPopover.classList.remove("hidden");
          fetchTripAdvisor();
        } else {
          tripAdvisorPopover.classList.add("hidden");
        }
      });
    }

    if (btnCloseTripAdvisor) {
      btnCloseTripAdvisor.addEventListener("click", () => {
        if (tripAdvisorPopover) tripAdvisorPopover.classList.add("hidden");
      });
    }

    // Travel Mode Buttons
    document.querySelectorAll("[data-mode]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const mode = btn.getAttribute("data-mode");
        state.currentTravelMode = mode;
        if (state.selectedStoreId) {
          fetchDirections(state.selectedStoreId, mode);
        }
      });
    });

    // Modals & Drawer Closes
    btnCloseDirections.addEventListener("click", () => {
      directionsDrawer.classList.remove("open");
      if (directionsAdvisorBox) directionsAdvisorBox.classList.add("hidden");
      state.activeDirections = null;
      renderMap();
    });

    btnCloseModal.addEventListener("click", () => {
      storeModal.classList.remove("open");
    });

    storeModal.addEventListener("click", (e) => {
      if (e.target === storeModal) storeModal.classList.remove("open");
    });

    // Trip Planner Listeners
    if (btnPlanTrip) btnPlanTrip.addEventListener("click", executeTripPlan);
    if (btnClearTrip) btnClearTrip.addEventListener("click", clearTripPlanner);
    if (btnCloseTripModal) {
      btnCloseTripModal.addEventListener("click", () => {
        tripModal.classList.remove("open");
      });
    }
    if (tripModal) {
      tripModal.addEventListener("click", (e) => {
        if (e.target === tripModal) tripModal.classList.remove("open");
      });
    }

    // Export and Print Handlers
    const tripBtnQr = document.getElementById("trip-btn-qr");
    const qrPopover = document.getElementById("qr-popover");
    const btnCloseQr = document.getElementById("btn-close-qr");
    const qrCanvasContainer = document.getElementById("qr-canvas-container");
    const qrUrlPreview = document.getElementById("qr-url-preview");
    const tripBtnExportGpx = document.getElementById("trip-btn-export-gpx");
    const tripBtnExportCsv = document.getElementById("trip-btn-export-csv");
    const tripBtnPrint = document.getElementById("trip-btn-print");

    if (tripBtnQr) {
      tripBtnQr.addEventListener("click", () => {
        if (!state.activeTripPlan || !state.activeTripPlan.google_maps_url) return;
        const url = state.activeTripPlan.google_maps_url;
        qrUrlPreview.textContent = url;
        qrCanvasContainer.innerHTML = `
          <img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(url)}"
               alt="Google Maps QR Code" width="180" height="180" style="display: block; border-radius: 4px;" />
        `;
        qrPopover.classList.remove("hidden");
      });
    }

    if (btnCloseQr) {
      btnCloseQr.addEventListener("click", () => {
        qrPopover.classList.add("hidden");
      });
    }

    if (tripBtnExportGpx) {
      tripBtnExportGpx.addEventListener("click", async () => {
        if (!state.activeTripPlan) return;
        try {
          const res = await fetch("/api/trip/export/gpx", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(state.activeTripPlan),
          });
          if (!res.ok) throw new Error("GPX export failed");
          const blob = await res.blob();
          const downloadUrl = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = `store_trip_route_${Date.now()}.gpx`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(downloadUrl);
        } catch (err) {
          alert(`Export failed: ${err.message}`);
        }
      });
    }

    if (tripBtnExportCsv) {
      tripBtnExportCsv.addEventListener("click", async () => {
        if (!state.activeTripPlan) return;
        try {
          const res = await fetch("/api/trip/export/csv", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(state.activeTripPlan),
          });
          if (!res.ok) throw new Error("CSV export failed");
          const blob = await res.blob();
          const downloadUrl = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = downloadUrl;
          a.download = `driver_delivery_manifest_${Date.now()}.csv`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(downloadUrl);
        } catch (err) {
          alert(`Export failed: ${err.message}`);
        }
      });
    }

    if (tripBtnPrint) {
      tripBtnPrint.addEventListener("click", () => {
        window.print();
      });
    }
  }

  // Geolocation handler
  function handleLocateMe() {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }
    btnLocateMe.disabled = true;
    btnLocateMe.innerHTML = `<span>Locating...</span>`;

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        btnLocateMe.disabled = false;
        btnLocateMe.innerHTML = `<span>Locate Me</span>`;
        state.origin = {
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          name: "Current Location",
        };
        searchInput.value = "Current Location";
        await performSearch();
      },
      (err) => {
        btnLocateMe.disabled = false;
        btnLocateMe.innerHTML = `<span>Locate Me</span>`;
        console.warn("Geolocation denied/failed, falling back to default.", err);
        alert("Could not access your location. Searching with default location.");
        performSearch();
      },
      { timeout: 8000 }
    );
  }

  // Search input handler
  async function handleSearchInput() {
    const q = searchInput.value.trim();
    if (!q) return;

    btnSearch.disabled = true;
    btnSearch.textContent = "Searching...";

    try {
      const res = await fetch(`/api/geocode?address=${encodeURIComponent(q)}`);
      if (res.ok) {
        const geo = await res.json();
        state.origin = {
          lat: geo.coordinates.latitude,
          lng: geo.coordinates.longitude,
          name: geo.formatted_address,
        };
      } else {
        console.warn("Geocode query unmatched; server will resolve coordinate fallback.");
        state.origin.name = q;
      }
      await performSearch();
    } catch (err) {
      console.error("Geocoding error:", err);
    } finally {
      btnSearch.disabled = false;
      btnSearch.textContent = "Search";
    }
  }

  // Perform Store Proximity Search
  async function performSearch() {
    resultsCount.textContent = "Searching stores...";
    resultsOrigin.textContent = `from ${state.origin.name}`;

    const params = new URLSearchParams({
      lat: state.origin.lat.toString(),
      lng: state.origin.lng.toString(),
      radius_km: state.radiusKm.toString(),
      origin_name: state.origin.name,
      sort_by: state.sortBy,
    });

    // Append active filter flags
    if (state.filters.open_now) params.append("open_now", "true");
    if (state.filters.rating_45) {
      params.append("min_rating", "4.5");
      params.append("rating_45", "true");
    }
    if (state.filters.drive_thru) params.append("drive_thru", "true");
    if (state.filters.curbside_pickup) params.append("curbside_pickup", "true");
    if (state.filters.ev_charging) params.append("ev_charging", "true");
    if (state.filters.wheelchair_accessible) params.append("wheelchair_accessible", "true");
    if (state.filters.wifi) params.append("wifi", "true");

    try {
      const res = await fetch(`/api/stores/search?${params.toString()}`);
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      state.stores = data.stores;

      resultsCount.textContent = `${data.total_found} ${data.total_found === 1 ? "location" : "locations"} nearby`;
      resultsOrigin.textContent = `near ${data.search_address}`;

      renderStoreList();
      renderMap();
    } catch (err) {
      console.error("Error fetching stores:", err);
      resultsCount.textContent = "Error finding stores";
      storeList.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger);">Failed to load store locations.</div>`;
    }
  }

  function resetAllFilters() {
    Object.keys(state.filters).forEach((k) => (state.filters[k] = false));
    document.querySelectorAll(".filter-chip").forEach((chip) => chip.classList.remove("active"));
    performSearch();
  }

  // Render Store Cards
  function renderStoreList() {
    if (!state.stores || state.stores.length === 0) {
      storeList.innerHTML = `
        <div style="padding: 30px; text-align: center; color: var(--text-muted);">
          <div style="font-size: 2.5rem; margin-bottom: 8px;">🔍</div>
          <strong style="color: var(--text); font-size: 1rem;">No matching stores found</strong>
          <p style="font-size: 0.85rem; margin-top: 6px;">
            No locations within ${state.radiusKm} km match your active filters.
          </p>
          <button id="btn-reset-filters" class="btn btn-secondary" style="margin-top: 14px; font-size: 0.82rem;">
            Reset All Filters
          </button>
        </div>
      `;
      const btnReset = document.getElementById("btn-reset-filters");
      if (btnReset) {
        btnReset.addEventListener("click", resetAllFilters);
      }
      return;
    }

    storeList.innerHTML = "";
    state.stores.forEach((item, index) => {
      const store = item.store;
      const isSelected = store.id === state.selectedStoreId;
      const isInTrip = state.tripStoreIds.includes(store.id);

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
          <button class="btn-trip-toggle ${isInTrip ? "in-trip" : ""}" data-action="toggle-trip" data-id="${store.id}">
            ${isInTrip ? "✓ In Trip" : "+ Trip"}
          </button>
          <button class="btn-card" data-action="details" data-id="${store.id}">Hours</button>
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

      card.querySelector('[data-action="toggle-trip"]').addEventListener("click", (e) => {
        e.stopPropagation();
        toggleStoreInTrip(store.id);
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

  // Fetch Single Store Directions
  async function fetchDirections(storeId, mode) {
    state.selectedStoreId = storeId;
    state.activeTripPlan = null; // Clear multi-stop when viewing single route
    directionsDrawer.classList.add("open");
    directionsSteps.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-muted);">Calculating turn-by-turn route...</div>`;

    try {
      const depTime = dirDepartureSelect ? dirDepartureSelect.value : state.departureTime;
      const trafModel = dirTrafficModel ? dirTrafficModel.value : state.trafficModel;
      const url = `/api/directions?origin_lat=${state.origin.lat}&origin_lng=${state.origin.lng}&destination_store_id=${storeId}&mode=${mode}&departure_time=${encodeURIComponent(depTime)}&traffic_model=${encodeURIComponent(trafModel)}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Directions request failed");
      const result = await res.json();

      state.activeDirections = result;
      directionsDistance.textContent = result.distance_text;
      directionsModeTitle.textContent = `${mode.charAt(0).toUpperCase() + mode.slice(1)} Route`;

      // Traffic Badge and Durations
      if (mode === "driving" && result.traffic_condition) {
        directionsTrafficBadge.classList.remove("hidden");
        const cond = result.traffic_condition.toLowerCase();
        directionsTrafficText.textContent = `Traffic: ${result.traffic_condition.toUpperCase()} Flow`;
        const delayMins = Math.round((result.traffic_delay_seconds || 0) / 60);
        directionsTrafficDelay.textContent = delayMins > 0 ? `+${delayMins} min delay` : "No Delay";

        if (cond === "clear") {
          directionsTrafficBadge.style.background = "#ecfdf5";
          directionsTrafficBadge.style.color = "#065f46";
          directionsTrafficBadge.style.borderColor = "#a7f3d0";
          directionsTrafficDelay.style.color = "#047857";
        } else if (cond === "moderate") {
          directionsTrafficBadge.style.background = "#fffbeb";
          directionsTrafficBadge.style.color = "#92400e";
          directionsTrafficBadge.style.borderColor = "#fde68a";
          directionsTrafficDelay.style.color = "#b45309";
        } else if (cond === "heavy") {
          directionsTrafficBadge.style.background = "#fff7ed";
          directionsTrafficBadge.style.color = "#9a3412";
          directionsTrafficBadge.style.borderColor = "#fed7aa";
          directionsTrafficDelay.style.color = "#c2410c";
        } else if (cond === "severe") {
          directionsTrafficBadge.style.background = "#fef2f2";
          directionsTrafficBadge.style.color = "#991b1b";
          directionsTrafficBadge.style.borderColor = "#fecaca";
          directionsTrafficDelay.style.color = "#dc2626";
        }

        if (result.duration_in_traffic_text) {
          directionsDuration.textContent = `Duration: ${result.duration_in_traffic_text} (In Traffic)`;
        } else {
          directionsDuration.textContent = `Estimated duration: ${result.duration_text}`;
        }
      } else {
        directionsTrafficBadge.classList.add("hidden");
        directionsDuration.textContent = `Estimated duration: ${result.duration_text}`;
      }

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
      console.error("Failed to load directions:", err);
      directionsSteps.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--danger);">Failed to calculate navigation route.</div>`;
    }
  }

  // Predictive Departure Advisor (Single Direction)
  async function fetchDirectionsAdvisor() {
    if (!state.selectedStoreId) return;
    dirAdvisorContent.innerHTML = `<div style="text-align: center; color: #166534; padding: 6px;">Simulating diurnal congestion curve...</div>`;
    try {
      const url = `/api/traffic/predict?origin=${state.origin.lat},${state.origin.lng}&destination_store_id=${state.selectedStoreId}&travel_mode=${state.currentTravelMode}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Advisor lookup failed");
      const data = await res.json();
      renderAdvisorBars(data, dirAdvisorContent);
    } catch (e) {
      dirAdvisorContent.innerHTML = `<div style="color: var(--danger); padding: 6px;">Failed to calculate departure forecast.</div>`;
    }
  }

  // Predictive Departure Advisor (Multi-Stop Trip)
  async function fetchTripAdvisor() {
    if (state.tripStoreIds.length === 0) return;
    tripAdvisorBars.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 10px;">Simulating trip departure windows...</div>`;
    try {
      const url = `/api/traffic/predict?origin=${state.origin.lat},${state.origin.lng}&store_ids=${state.tripStoreIds.join(",")}&travel_mode=${state.currentTravelMode}&round_trip=${tripRoundTrip.checked}&optimize=${tripOptimize.checked}`;
      const res = await fetch(url);
      if (!res.ok) throw new Error("Advisor lookup failed");
      const data = await res.json();
      renderAdvisorBars(data, tripAdvisorBars);
    } catch (e) {
      tripAdvisorBars.innerHTML = `<div style="color: var(--danger); padding: 8px;">Failed to calculate departure forecast.</div>`;
    }
  }

  // Helper to render horizontal comparison bars for departure windows
  function renderAdvisorBars(data, container) {
    const maxDur = Math.max(...data.predictions.map((p) => p.duration_in_traffic_seconds), 1);
    const bestSavedMins = Math.round(data.max_time_saved_seconds / 60);

    let html = `
      <div style="margin-bottom: 8px; font-size: 0.8rem; font-weight: 600; line-height: 1.4;">
        💡 Recommendation: <span style="color: #15803d;">${escapeHtml(data.best_window.label)}</span>
        ${bestSavedMins > 0 ? `saves ~<strong>${bestSavedMins} mins</strong> over ${escapeHtml(data.worst_window.label)}.` : "has minimal congestion."}
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px;">
    `;

    data.predictions.forEach((pred) => {
      const pct = Math.max(18, Math.round((pred.duration_in_traffic_seconds / maxDur) * 100));
      const isBest = pred.window_key === data.best_window.window_key;
      const isWorst = pred.window_key === data.worst_window.window_key;
      const barColor = isBest ? "#10b981" : isWorst ? "#ef4444" : "#f59e0b";
      const badge = isBest
        ? `<span style="font-size: 0.68rem; background: #dcfce7; color: #166534; padding: 2px 6px; border-radius: 8px; font-weight: 700; margin-left: 6px;">BEST TIME</span>`
        : isWorst
        ? `<span style="font-size: 0.68rem; background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 8px; font-weight: 700; margin-left: 6px;">PEAK RUSH</span>`
        : "";

      html += `
        <div style="font-size: 0.76rem;">
          <div style="display: flex; justify-content: space-between; margin-bottom: 3px;">
            <span><strong>${escapeHtml(pred.label)}</strong> (${pred.time_range}) ${badge}</span>
            <span><strong>${pred.duration_in_traffic_text}</strong> <span style="color: var(--text-muted); font-size: 0.72rem;">(${pred.traffic_condition})</span></span>
          </div>
          <div style="width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden;">
            <div style="width: ${pct}%; height: 100%; background: ${barColor}; border-radius: 4px; transition: width 0.3s ease;"></div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  // =========================================================================
  // Multi-Stop Trip Planner Controller
  // =========================================================================

  function toggleStoreInTrip(storeId) {
    const idx = state.tripStoreIds.indexOf(storeId);
    if (idx > -1) {
      state.tripStoreIds.splice(idx, 1);
    } else {
      if (state.tripStoreIds.length >= 10) {
        alert("Maximum of 10 store destinations per trip.");
        return;
      }
      state.tripStoreIds.push(storeId);
    }

    updateTripBarUI();
    renderStoreList();
    renderMap();
  }

  function updateTripBarUI() {
    if (!tripBar) return;
    const count = state.tripStoreIds.length;

    if (count === 0) {
      tripBar.classList.add("hidden");
      return;
    }

    tripBar.classList.remove("hidden");
    tripCountBadge.textContent = count;

    // Render Pills
    tripStorePills.innerHTML = "";
    state.tripStoreIds.forEach((sid) => {
      const storeItem = state.stores.find((s) => s.store.id === sid);
      const name = storeItem ? storeItem.store.name.replace("Apex Retail - ", "") : `Store #${sid}`;
      const pill = document.createElement("span");
      pill.className = "trip-store-pill";
      pill.innerHTML = `
        <span>${escapeHtml(name)}</span>
        <span class="trip-store-pill-remove" data-remove-id="${sid}">&times;</span>
      `;
      pill.querySelector(".trip-store-pill-remove").addEventListener("click", (e) => {
        e.stopPropagation();
        toggleStoreInTrip(sid);
      });
      tripStorePills.appendChild(pill);
    });
  }

  function clearTripPlanner() {
    state.tripStoreIds = [];
    state.activeTripPlan = null;
    updateTripBarUI();
    renderStoreList();
    renderMap();
  }

  async function executeTripPlan() {
    if (state.tripStoreIds.length < 2) {
      alert("Please select at least 2 store destinations to calculate an optimized trip.");
      return;
    }

    btnPlanTrip.disabled = true;
    btnPlanTrip.textContent = "Optimizing Route...";

    try {
      const depTime = tripDepartureSelect ? tripDepartureSelect.value : state.departureTime;
      const trafModel = tripTrafficModel ? tripTrafficModel.value : state.trafficModel;
      const payload = {
        origin: `${state.origin.lat},${state.origin.lng}`,
        store_ids: state.tripStoreIds,
        round_trip: tripRoundTrip.checked,
        optimize: tripOptimize.checked,
        travel_mode: state.currentTravelMode,
        departure_time: depTime,
        traffic_model: trafModel,
      };

      const res = await fetch("/api/trip/plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to calculate trip itinerary");
      }

      const plan = await res.json();
      state.activeTripPlan = plan;
      state.activeDirections = null; // Clear single route
      directionsDrawer.classList.remove("open");

      openTripModal(plan);
      renderMap();
    } catch (err) {
      console.error("Trip planning error:", err);
      alert(`Trip Planning Error: ${err.message}`);
    } finally {
      btnPlanTrip.disabled = false;
      btnPlanTrip.textContent = "🚀 Calculate Route";
    }
  }

  function openTripModal(plan) {
    if (!tripModal) return;

    // Savings banner
    if (plan.savings) {
      tripSavingsBanner.classList.remove("hidden");
      tripSavingsTitle.textContent = `TSP Optimization Saved ${plan.savings.distance_saved_miles.toFixed(1)} mi (${plan.savings.percentage_distance_saved.toFixed(1)}%)`;
      tripSavingsDesc.textContent = `Estimated ~${Math.round(plan.savings.estimated_minutes_saved)} mins travel time saved over naive visiting sequence.`;
    } else {
      tripSavingsBanner.classList.add("hidden");
    }

    // Traffic Flow Banner
    if (plan.traffic_condition && plan.travel_mode === "driving") {
      tripTrafficBanner.classList.remove("hidden");
      const cond = plan.traffic_condition.toLowerCase();
      const delayMins = Math.round((plan.total_traffic_delay_seconds || 0) / 60);
      tripTrafficTitle.textContent = `Traffic Flow: ${plan.traffic_condition.toUpperCase()} (${plan.traffic_model ? plan.traffic_model.replace('_', ' ') : 'best guess'})`;
      tripTrafficDesc.textContent = delayMins > 0
        ? `Estimated +${delayMins} min congestion delay across all route legs.`
        : "Optimal traffic flow with minimal delay along this multi-stop itinerary.";
      tripTrafficDelayBadge.textContent = delayMins > 0 ? `+${delayMins}m delay` : "Smooth Flow";

      if (cond === "clear") {
        tripTrafficBanner.style.background = "#ecfdf5";
        tripTrafficBanner.style.borderColor = "#a7f3d0";
        tripTrafficTitle.style.color = "#065f46";
        tripTrafficDelayBadge.style.background = "#d1fae5";
        tripTrafficDelayBadge.style.color = "#065f46";
      } else if (cond === "moderate") {
        tripTrafficBanner.style.background = "#fffbeb";
        tripTrafficBanner.style.borderColor = "#fde68a";
        tripTrafficTitle.style.color = "#92400e";
        tripTrafficDelayBadge.style.background = "#fef3c7";
        tripTrafficDelayBadge.style.color = "#92400e";
      } else if (cond === "heavy") {
        tripTrafficBanner.style.background = "#fff7ed";
        tripTrafficBanner.style.borderColor = "#fed7aa";
        tripTrafficTitle.style.color = "#9a3412";
        tripTrafficDelayBadge.style.background = "#ffedd5";
        tripTrafficDelayBadge.style.color = "#9a3412";
      } else if (cond === "severe") {
        tripTrafficBanner.style.background = "#fef2f2";
        tripTrafficBanner.style.borderColor = "#fecaca";
        tripTrafficTitle.style.color = "#991b1b";
        tripTrafficDelayBadge.style.background = "#fee2e2";
        tripTrafficDelayBadge.style.color = "#991b1b";
      }

      if (tripStatTrafficSub) {
        tripStatTrafficSub.textContent = delayMins > 0
          ? `(${plan.total_duration_in_traffic_text} in traffic)`
          : "clear flow";
      }
    } else {
      tripTrafficBanner.classList.add("hidden");
      if (tripStatTrafficSub) tripStatTrafficSub.textContent = "";
    }

    // Stats Grid
    tripStatDistance.textContent = plan.total_distance_text;
    tripStatDuration.textContent = plan.total_duration_in_traffic_text || plan.total_duration_text;
    tripStatStops.textContent = `${plan.stops.length} stops (${plan.legs.length} legs)`;
    tripStatMode.textContent = plan.travel_mode.charAt(0).toUpperCase() + plan.travel_mode.slice(1);

    // Update Universal Google Maps Navigation Link
    const tripBtnGoogleMaps = document.getElementById("trip-btn-google-maps");
    if (tripBtnGoogleMaps && plan.google_maps_url) {
      tripBtnGoogleMaps.href = plan.google_maps_url;
    }

    // Sequential Stops Timeline
    tripStopsTimeline.innerHTML = "";
    plan.stops.forEach((stop) => {
      const item = document.createElement("div");
      item.className = "timeline-item";
      const isOrig = stop.is_origin;
      const isRet = stop.is_destination && !stop.is_origin && stop.store_id === null;
      const badgeClass = isOrig ? "origin" : isRet ? "return" : "";
      const label = isOrig ? "A" : isRet ? "★" : String(stop.sequence_index);

      item.innerHTML = `
        <div class="timeline-badge ${badgeClass}">${label}</div>
        <div class="timeline-content">
          <div class="timeline-name">${escapeHtml(stop.name)}</div>
          <div class="timeline-address">${escapeHtml(stop.address)}</div>
        </div>
      `;
      tripStopsTimeline.appendChild(item);
    });

    // Navigation Legs
    tripLegsContainer.innerHTML = "";
    plan.legs.forEach((leg, idx) => {
      const card = document.createElement("div");
      card.className = "leg-card";
      const legDelayMins = Math.round((leg.traffic_delay_seconds || 0) / 60);
      const legDelayBadge = legDelayMins > 0
        ? ` <span style="color: #b45309; font-weight: 600; font-size: 0.75rem;">(+${legDelayMins}m traffic)</span>`
        : "";
      card.innerHTML = `
        <div class="leg-header">
          <span class="leg-title">Leg ${idx + 1}: ${escapeHtml(leg.start_node.name.slice(0, 24))} &rarr; ${escapeHtml(leg.end_node.name.slice(0, 24))}</span>
          <span class="leg-meta">${leg.distance_text} · ${leg.duration_in_traffic_text || leg.duration_text}${legDelayBadge}</span>
        </div>
      `;
      tripLegsContainer.appendChild(card);
    });

    tripModal.classList.add("open");
  }

  // Open Store Modal Details
  function openStoreModal(store) {
    document.getElementById("modal-store-name").textContent = store.name;
    document.getElementById("modal-store-brand").textContent = `${store.brand} — Store #${store.id}`;
    document.getElementById("modal-store-address").textContent = store.full_address;
    document.getElementById("modal-store-phone").textContent = store.phone || "No phone listed";

    // Weekly hours schedule
    const tbody = document.getElementById("modal-hours-body");
    tbody.innerHTML = "";
    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    const nowDay = new Date().toLocaleDateString("en-US", { weekday: "long" }).toLowerCase();

    days.forEach((d) => {
      const dh = store.hours[d];
      const isToday = d === nowDay;
      const tr = document.createElement("tr");
      if (isToday) tr.className = "today";
      tr.innerHTML = `
        <td style="font-weight: 600; text-transform: capitalize;">${d} ${isToday ? "(Today)" : ""}</td>
        <td style="text-align: right; ${dh.is_closed ? "color: var(--danger);" : ""}">${dh.is_closed ? "Closed" : `${format12(dh.open_time)} – ${format12(dh.close_time)}`}</td>
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

  // Helper to decode Google polyline strings into array of {lat, lng}
  function decodePolylineJs(str) {
    if (!str) return [];
    let index = 0, lat = 0, lng = 0, coordinates = [];
    while (index < str.length) {
      let b, shift = 0, result = 0;
      do {
        b = str.charCodeAt(index++) - 63;
        result |= (b & 0x1f) << shift;
        shift += 5;
      } while (b >= 0x20);
      lat += ((result & 1) ? ~(result >> 1) : (result >> 1));
      shift = 0;
      result = 0;
      do {
        b = str.charCodeAt(index++) - 63;
        result |= (b & 0x1f) << shift;
        shift += 5;
      } while (b >= 0x20);
      lng += ((result & 1) ? ~(result >> 1) : (result >> 1));
      coordinates.push({ lat: lat / 1e5, lng: lng / 1e5 });
    }
    return coordinates;
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

    // Build Route Polyline Path with Real-Time Traffic Segments
    let polylineSvg = "";

    // Multi-stop trip polyline takes precedence if active
    if (state.activeTripPlan) {
      let tripSegsSvg = "";
      if (state.activeTripPlan.legs && state.activeTripPlan.legs.some((l) => l.traffic_segments && l.traffic_segments.length > 0)) {
        state.activeTripPlan.legs.forEach((leg) => {
          if (leg.traffic_segments && leg.traffic_segments.length > 0) {
            leg.traffic_segments.forEach((seg) => {
              const segCoords = decodePolylineJs(seg.polyline);
              if (segCoords.length >= 2) {
                const pts = segCoords.map((c) => {
                  const pt = project(c.lat, c.lng);
                  return `${pt.x},${pt.y}`;
                }).join(" ");
                tripSegsSvg += `
                  <polyline points="${pts}" fill="none" stroke="${seg.color_hex}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity="0.9" />
                  <polyline points="${pts}" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.3" />
                `;
              }
            });
          }
        });
      }

      if (tripSegsSvg) {
        polylineSvg = tripSegsSvg;
      } else if (state.activeTripPlan.overview_polyline) {
        const tripCoords = decodePolylineJs(state.activeTripPlan.overview_polyline);
        if (tripCoords.length > 0) {
          const pts = tripCoords.map((c) => {
            const pt = project(c.lat, c.lng);
            return `${pt.x},${pt.y}`;
          });
          polylineSvg = `
            <polyline points="${pts.join(" ")}" fill="none" stroke="#7c3aed" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity="0.85" />
            <polyline points="${pts.join(" ")}" fill="none" stroke="#a78bfa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
          `;
        }
      }
    } else if (state.activeDirections) {
      if (state.activeDirections.traffic_segments && state.activeDirections.traffic_segments.length > 0) {
        polylineSvg = state.activeDirections.traffic_segments.map((seg) => {
          const segCoords = decodePolylineJs(seg.polyline);
          if (segCoords.length < 2) return "";
          const pts = segCoords.map((c) => {
            const pt = project(c.lat, c.lng);
            return `${pt.x},${pt.y}`;
          }).join(" ");
          return `
            <polyline points="${pts}" fill="none" stroke="${seg.color_hex}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" opacity="0.95" />
            <polyline points="${pts}" fill="none" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" opacity="0.35" />
          `;
        }).join("");
      } else if (state.activeDirections.route_coordinates) {
        const pts = state.activeDirections.route_coordinates.map((c) => {
          const pt = project(c.latitude, c.longitude);
          return `${pt.x},${pt.y}`;
        });
        polylineSvg = `
          <polyline points="${pts.join(" ")}" fill="none" stroke="#2563eb" stroke-width="5" stroke-linecap="round" stroke-linejoin="round" opacity="0.9" />
          <polyline points="${pts.join(" ")}" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        `;
      }
    }

    // Build Store Pin Markers
    let markersSvg = "";
    stores.forEach((item, index) => {
      const st = item.store;
      const pt = project(st.latitude, st.longitude);
      const isSelected = st.id === state.selectedStoreId;
      const isInTrip = state.tripStoreIds.includes(st.id);

      // Check if store is sequenced in active trip plan
      let tripOrderLabel = null;
      if (state.activeTripPlan) {
        const stopNode = state.activeTripPlan.stops.find((s) => s.store_id === st.id);
        if (stopNode) tripOrderLabel = stopNode.sequence_index;
      }

      let pinColor = item.is_open_now ? "#10b981" : "#ef4444";
      if (tripOrderLabel !== null) pinColor = "#7c3aed"; // Purple for trip stops
      else if (isInTrip) pinColor = "#2563eb";

      const scale = isSelected || tripOrderLabel !== null ? 1.3 : 1.0;
      const labelText = tripOrderLabel !== null ? `★${tripOrderLabel}` : String(index + 1);

      markersSvg += `
        <g class="map-pin" data-store-id="${st.id}" transform="translate(${pt.x}, ${pt.y}) scale(${scale})" style="cursor: pointer;">
          <circle cx="0" cy="0" r="${isSelected ? 18 : 14}" fill="${pinColor}" stroke="#ffffff" stroke-width="2.5" filter="drop-shadow(0px 3px 3px rgba(0,0,0,0.25))" />
          <text x="0" y="4" font-size="${tripOrderLabel !== null ? 9 : 11}" font-weight="bold" fill="#ffffff" text-anchor="middle" font-family="sans-serif">${labelText}</text>
          ${isSelected ? `<circle cx="0" cy="0" r="22" fill="none" stroke="#2563eb" stroke-width="2.5" stroke-dasharray="3,3" />` : ""}
          ${isInTrip ? `<circle cx="0" cy="0" r="20" fill="none" stroke="#7c3aed" stroke-width="2" />` : ""}
        </g>
      `;
    });

    // Render Real-Time Arterial Traffic Layer if active
    let trafficOverlaySvg = "";
    if (state.trafficLayerEnabled) {
      if (state.trafficOverlayData && state.trafficOverlayData.length > 0) {
        state.trafficOverlayData.forEach((art) => {
          const p1 = project(art.start_lat, art.start_lng);
          const p2 = project(art.end_lat, art.end_lng);
          trafficOverlaySvg += `
            <line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="${art.color_hex}" stroke-width="7" stroke-linecap="round" opacity="0.8" />
            <line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="#ffffff" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.5" />
          `;
        });
      } else {
        trafficOverlaySvg = `
          <line x1="0" y1="${height * 0.45}" x2="${width}" y2="${height * 0.45}" stroke="#f59e0b" stroke-width="7" opacity="0.8" />
          <line x1="${width * 0.52}" y1="0" x2="${width * 0.52}" y2="${height}" stroke="#ef4444" stroke-width="7" opacity="0.8" />
        `;
      }
    }

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

          <!-- Real-Time Traffic Arterial Overlay (When active) -->
          ${trafficOverlaySvg}

          <!-- Active Navigation Polyline -->
          ${polylineSvg}

          <!-- User Origin Radar Pin -->
          <g transform="translate(${originPt.x}, ${originPt.y})">
            <circle cx="0" cy="0" r="18" fill="#3b82f6" opacity="0.25">
              <animate attributeName="r" values="12;24;12" dur="2.5s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.4;0.05;0.4" dur="2.5s" repeatCount="indefinite"/>
            </circle>
            <circle cx="0" cy="0" r="8" fill="#2563eb" stroke="#ffffff" stroke-width="2.5"/>
            <text x="0" y="3" font-size="8" font-weight="bold" fill="#ffffff" text-anchor="middle" font-family="sans-serif">A</text>
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

        <div style="position: absolute; bottom: 12px; left: 16px; background: rgba(255,255,255,0.92); padding: 6px 12px; border-radius: 6px; font-size: 0.75rem; border: 1px solid var(--border); box-shadow: var(--shadow); display: flex; align-items: center; gap: 8px;">
          <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #10b981; vertical-align: middle; margin-right: 3px;"></span> Open</span>
          <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #ef4444; vertical-align: middle; margin-right: 3px;"></span> Closed</span>
          <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #7c3aed; vertical-align: middle; margin-right: 3px;"></span> Trip Stop</span>
          <span><span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #2563eb; vertical-align: middle; margin-right: 3px;"></span> Origin</span>
          ${state.trafficLayerEnabled ? `<span><span style="display: inline-block; width: 14px; height: 4px; border-radius: 2px; background: #f59e0b; vertical-align: middle; margin-right: 3px;"></span> Live Traffic</span>` : ""}
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
