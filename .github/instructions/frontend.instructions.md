---
applyTo: 'frontend/**'
---

# Frontend (React/TypeScript) - Port 3000

## Tech Map / Key Files

**Application Architecture:**
- `frontend/src/main.tsx` - React entry point: `StrictMode` → `ErrorProvider` → `App`
- `frontend/src/App.tsx` - Main app with nested providers: `ErrorBoundary` → `ThemeProvider` → `ConfigProvider` → `AuthProvider` → `BrowserRouter`; side-effect imports `./utils/devTools`
- `frontend/src/config.ts` - **CRITICAL**: Configuration management with dynamic loading
- `frontend/public/config/config.json` - Runtime configuration (backendUrl, ingestorUrl)
- `frontend/src/errors.ts` - Client error reporting system: opt-in (localStorage flag), localStorage queue with dedup, batch flush (5s throttle, max 25), 60s cooldown per error fingerprint

### Context & State Management (`frontend/src/context/`)
- `AuthContext.tsx` - JWT-based authentication context with multi-role support. Exports: `UserRole`, `User`, `AuthProvider`, `useAuth()`, `useAuthHeader()`. Token verification on mount, auto-refresh on 401, `useMemo` for context value. Legacy support: `username` defaults to `user?.username || 'guest'`.
- `ConfigContext.tsx` - Global configuration context with dynamic loading, blocks rendering until loaded, fallback to `{ backendUrl: '/api', ingestorUrl: '/api' }`
- `ErrorContext.tsx` - Error handling with `react-toastify` toasts, `ErrorRecord[]` ring buffer (max 100), `ErrorCenter` modal, `startErrorQueueFlusher()` on mount
- `ThemeContext.tsx` - Theme management (light/dark mode)
- `auth/` - (empty directory, reserved for future auth utilities)

### Custom Hooks (`frontend/src/hooks/`)
- `useDashboardData.ts` - Manages 4 parallel data streams (temperature, Spark master/streams, alerts). Uses `useRef` to distinguish initial load vs refresh (avoids skeleton on refresh). 15s auto-refresh. `refreshAll()` does `Promise.all` of all 4 fetches. Data preserved on error.
- `usePipelineData.ts` - Consolidates ALL pipeline page state: partitions, sensor data, devices, normalization rules, value transformations, computations. `Promise.all` for 4 parallel fetches. Sensor data auto-refreshes every 5s. Dynamic table column detection with preferred order. Device form state managed inside hook. Uses `useAuth().username` for attribution.
- `useErrorCapture.ts` - Rich error capture with context (`component`, `action`, `props`, `state`, `user`). `wrapAsync`/`wrapSync` (re-throw after capture), `safeAsync`/`safeSync` (return fallback). `setupGlobalErrorHandlers()` for `unhandledrejection`, `error` events.

### API Integration (`frontend/src/api/`)
- `backendRequests.tsx` - **COMPREHENSIVE** (~1500 lines): Central `doFetch<T>()` function wraps all API calls with:
  - Auto auth header injection via `withAuth` from `authUtils`
  - Automatic 401 → token refresh → retry
  - Response unwrapping (`ApiResponse<T>.data`)
  - Dev logging, enhanced error metadata
  - Uses `fetchWithErrorHandling` from `networkErrorHandler`

  Domain groups: Sensor Data, Spark, Buildings, Feedback, MinIO, Normalization, Value Transformations, Computations, Dashboard Tiles, Devices, Config, Settings, Normalization Preview, Errors, Copilot, Data Sources (ingestor), Metadata (ingestor), Ingestor Diagnostics, Test Users

### TypeScript Types (`frontend/src/types/`)
- `dataSource.ts` - `DataSourceType`, `DataSource`, `CreateDataSourceRequest`, `UpdateDataSourceRequest`, `DataSourceHealth`, `ConnectorStatusOverview`, `JsonSchema`/`JsonSchemaProperty` for dynamic form generation
- `valueTransformation.ts` - `TransformationType`, `ValueTransformationRule`, explicit config interfaces per transformation type (Filter/Aggregate/Convert/Validate)
- `imports.d.ts` - Module declarations for non-TS imports

### Component Architecture (`frontend/src/components/`)

**Core Dashboard Components:**
- `DashboardGrid.tsx` - React-grid-layout integration with drag & drop
- `DashboardTile.tsx` - Pure visualization component (table/stat/timeseries)
- `TileWithData.tsx` - **CRITICAL**: Data fetching, auto-refresh, and chart rendering
- `TileModal.tsx` - Tile creation/editing with live preview
- `DashboardHeader.tsx` - Dashboard controls and settings

**Data Visualization & Status Cards:**
- `TemperatureChart.tsx` - Time series temperature visualization
- `StatisticsCards.tsx` - System metrics display
- `SparkApplicationsCard.tsx` - Spark cluster status
- `TemperatureAlertsCard.tsx` - Real-time alert display
- `EnrichmentStatusCard.tsx` - Data pipeline status
- `ValueTransformationStatusCard.tsx` - Transformation rule status

**Pipeline Components (`pipeline/`):**
- `PipelineNavigationSidebar.tsx` - Navigation sidebar with rule counts
- `PipelineOverview.tsx` - Pipeline status overview card
- `PipelineOverviewTab.tsx` - Overview tab content
- `SensorDataTab.tsx` - Sensor data browsing tab
- `NormalizationTab.tsx` - Normalization rules management tab
- `NormalizationRulesSection.tsx` - Normalization rules table and CRUD
- `ValueTransformationsTab.tsx` - Value transformation rules management with full CRUD, field selection, and examples
- `ComputationsTab.tsx` - SQL computations tab
- `ComputationsSection.tsx` - Computations table and management
- `DevicesTab.tsx` - Device registration and management tab
- `SchemaConfiguration.tsx` - Schema configuration component

**Computations Components (`computations/`):**
- `ComputationsTable.tsx` - Computations list and management table
- `CopilotAssistant.tsx` - AI-powered SQL generation assistant
- `DefinitionValidator.ts` - SQL definition validation utilities
- `PreviewModal.tsx` - Computation result preview modal

**Sensor Data Components (`sensor-data/`):**
- `DataViewer.tsx` - Sensor data viewer component
- `DevicesTableCard.tsx` - Devices table card component
- `EnrichmentDiagnosticCard.tsx` - Enrichment diagnostic card
- `RegisterDeviceCard.tsx` - Device registration card
- `TopControlsBar.tsx` - Top controls bar for sensor data

**Navigation & Layout:**
- `AppNavbar.tsx` - Main application navigation bar with auth integration
- `PageHeader.tsx` - Reusable page header component
- `Footer.tsx` - Application footer
- `ProtectedRoute.tsx` - Role-based route protection component (exists but not currently wrapping any routes in App.tsx)
- `UserSwitcher.tsx` - Dev-mode test user switching dropdown (calls `getTestUsers()` API, role-based icons, quick switch via logout→login→reload)

**Utility & Support Components:**
- `ErrorBoundary.tsx` - Global error handling wrapper
- `withErrorBoundary.tsx` - HOC for error boundary
- `ErrorCenter.tsx` - Error logging and display center
- `DevErrorOverlay.tsx` - Development error overlay
- `ErrorTestComponent.tsx` - Error testing component
- `DebugPanel.tsx` - Debug information panel
- `DebugFloatingButton.tsx` - Floating debug button (rendered globally in App.tsx)
- `MetadataViewer.tsx` - JSON data inspector
- `ThemedReactJson.tsx` - Styled JSON viewer with theme support
- `ThemedTable.tsx` - Themed table component
- `WithTooltip.tsx` - Reusable tooltip wrapper
- `DynamicConfigForm.tsx` - Dynamic form configuration
- `DynamicFields.tsx` - Dynamic field rendering
- `NormalizationPreviewModal.tsx` - Normalization preview modal
- `NewBuildingModal.tsx` - New building creation modal
- `OntologyViewer.tsx` - Ontology graph viewer
- `SensorForm.tsx` - Sensor registration form
- `SensorData.tsx` - Sensor data display component
- `TemperatureThresholdModal.tsx` - Temperature threshold configuration modal

### Pages (`frontend/src/pages/`)
- `Home.tsx` - Landing page with system overview
- `DashboardPage.tsx` - **MAIN**: Modular dashboard with user-defined tiles
- `DataPipelinePage.tsx` - **COMPREHENSIVE**: Unified pipeline management with tabs for sensors, normalization, transformations, computations, and devices
- `DataSourcesPage.tsx` - Ingestor data source management (MQTT, REST API)
- `MonitoringPage.tsx` - Dedicated monitoring page with Spark status and enrichment cards (uses `useDashboardData()` hook)
- `MinioBrowserPage.tsx` - Object storage browser and file explorer
- `MetadataPage.tsx` - Schema metadata explorer with field statistics
- `SettingsPage.tsx` - Application settings and configuration
- `OntologyPage.tsx` - Neo4j graph visualization and building management
- `FeedbackPage.tsx` - User feedback and bug report collection
- `NewEventsPage.tsx` - Event monitoring and alerts
- `MapPage.tsx` - Geospatial visualization (if enabled)
- `LoginPage.tsx` - Login and registration page with multi-role support

**Frontend Routes** (in `App.tsx`):
`/`, `/login`, `/pipeline`, `/dashboard`, `/monitoring`, `/ontology`, `/map`, `/settings`, `/feedback`, `/minio`, `/metadata`, `/data-sources`, `/new-events`

### Utilities (`frontend/src/utils/`)
- `timeUtils.ts` - **CRITICAL**: Time formatting for refresh intervals and relative time display
- `authUtils.ts` - Authentication utilities (`getAuthHeaders`, `withAuth`, `tryRefreshToken`, `clearAuthData`), dispatches auth events (`logout`, `tokenRefreshed`)
- `errorHandling.ts` - Error message extraction: `extractErrorMessage(error, default)`, plus domain-specific extractors (`extractComputationErrorMessage`, `extractDashboardTileErrorMessage`, `extractPreviewErrorMessage`, `extractDeleteErrorMessage`). Strips HTTP status code prefixes.
- `networkErrorHandler.ts` - Singleton `NetworkErrorHandler` with listener pattern, wraps `fetch()` to create structured `NetworkError` objects, user-friendly toast messages by status range, dedup via `toastId`, `useNetworkErrorHandler()` React hook (keeps last 50 errors)
- `devTools.ts` - Dev-only utilities: global `window.__SOAM_DEV_TOOLS__` object, keyboard shortcut `Ctrl+Shift+D` for debug panel, `withErrorCapture<T>()`/`withAsyncErrorCapture<T>()` function wrappers, `useComponentErrorHandler(componentName)` React hook. Auto-initializes on import in dev mode.
- `numberUtils.ts` - Numeric formatting: `formatNumber(value, decimals)`, `isNumericValue(value)`, `formatDisplayValue(value)` (→ string for UI, null→'—'), `roundNumericValue(value, decimals)` (→ number for charts)

### Models (`frontend/src/models/`)
- `Building.tsx` - Building model type

## Frontend Development Patterns

### 1. Modular Dashboard System (CRITICAL)
**Pattern**: Component-based architecture with time series chart support and auto-refresh

```typescript
// Core dashboard components
frontend/src/components/TileWithData.tsx      - Data fetching, refresh logic, chart rendering
frontend/src/components/TileModal.tsx         - Tile creation/editing with live preview
frontend/src/components/DashboardTile.tsx     - Chart/table/stat visualization component
frontend/src/components/DashboardGrid.tsx     - Grid layout with drag-and-drop
frontend/src/components/DashboardHeader.tsx   - Dashboard controls and settings
frontend/src/hooks/useDashboardData.ts        - Dashboard data fetching hook
frontend/src/utils/timeUtils.ts              - Time formatting utilities

// Backend support
backend/src/api/dashboard_tiles_routes.py    - CRUD operations for user-defined tiles
backend/src/dashboard/examples.py            - Predefined tile templates with smart computation matching
```

**Key Features**:
- **Time Series Support**: LineChart with recharts, configurable time/value fields
- **Auto-Refresh**: Configurable intervals with throttling and concurrent request prevention
- **Live Preview**: Real-time tile preview during configuration
- **Drag & Drop**: React-grid-layout integration for dashboard customization
- **Type Safety**: Full TypeScript integration with backend response models
- **Smart Examples**: `get_tile_examples(db)` matches templates to available computations by `recommended_tile_type`

**Critical Implementation Details**:
```typescript
// TileWithData.tsx - Proper useEffect dependency management to prevent infinite loops
useEffect(() => {
  // Data fetching logic
}, [tile.id, tsKey]); // ❌ NEVER include 'rows' in dependencies

// Auto-refresh with minimum interval safety
const safeRefreshInterval = Math.max(refreshIntervalMs, 15000); // Minimum 15 seconds

// Time series configuration in tile.config
{
  "timeField": "time_start",      // X-axis field
  "valueField": "avg_temperature", // Y-axis field
  "chartHeight": 250,             // Chart height in pixels
  "refreshInterval": 30000,       // Refresh interval in milliseconds
  "autoRefresh": true             // Enable/disable auto-refresh
}
```

### 2. API Integration Pattern
**Location**: `frontend/src/api/backendRequests.tsx`

**Central `doFetch<T>()` pattern**:
```typescript
// All API calls go through doFetch which provides:
// 1. Auto auth header injection (withAuth from authUtils)
// 2. Automatic 401 → token refresh → retry
// 3. Response unwrapping (ApiResponse<T>.data)
// 4. Dev logging
// 5. Enhanced error metadata via fetchWithErrorHandling

// Example API function pattern:
export async function listDevices(): Promise<Device[]> {
  return doFetch<Device[]>(`${backendUrl}/api/devices`);
}

export async function registerDevice(payload: RegisterDevicePayload): Promise<Device> {
  return doFetch<Device>(`${backendUrl}/api/devices`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
```

### 3. Custom Hook Pattern
**Location**: `frontend/src/hooks/`

```typescript
// useDashboardData.ts - Manages 4 parallel data streams
const {
  averageTemperature, loading, refreshingTemperature,
  sparkMasterStatus, sparkStreamsStatus, temperatureAlerts,
  autoRefresh, setAutoRefresh, refreshAll, lastUpdated
} = useDashboardData();

// usePipelineData.ts - Consolidates ALL pipeline page state (~30 values)
const {
  activePartition, sensorData, devices, normalizationRules,
  valueTransformationRules, computations, tableColumns,
  handleRegisterDevice, handleToggleDevice, handleDeleteDevice,
  // ... many more
} = usePipelineData();

// Pattern: useRef to distinguish initial load vs refresh
const isInitialLoad = useRef(true);
// Show skeleton only on initial load, not on refresh
```

### 4. Authentication Context
```typescript
// AuthContext.tsx - Key exports
const { user, isAdmin, hasRole, hasAllRoles, logout, username } = useAuth();
const authHeader = useAuthHeader();  // Returns { Authorization: "Bearer ..." }

// hasRole checks ANY of specified roles
if (hasRole('admin', 'user')) { /* user has admin OR user role */ }

// hasAllRoles checks ALL specified roles
if (hasAllRoles('admin', 'user')) { /* user has BOTH roles */ }

// username fallback for backward-compatible attribution
// Defaults to user?.username || 'guest'
```

### 5. Multi-Layer Error Handling
- `ErrorContext` (toasts via react-toastify) → `networkErrorHandler` (HTTP-level) → `useErrorCapture` (component-level) → `errors.ts` (queue + backend reporting) → `devTools` (dev instrumentation)
- Client errors batched and flushed to backend via `/api/errors`

## Frontend Code Conventions
```powershell
cd frontend
npm run lint
npm run build
npm run preview
```

- API calls use `doFetch<T>()` pattern in `backendRequests.tsx`
- Data fetching extracted into custom hooks (not inline in components)
- Errors extracted with `extractErrorMessage()` utilities
- `useAuth().username` used for attribution
- React Bootstrap for consistent styling
- TypeScript types in `/frontend/src/types/` (avoid type duplication with `backendRequests.tsx`)
