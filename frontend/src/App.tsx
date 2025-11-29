import { Routes, Route, BrowserRouter } from 'react-router-dom';
import './App.css';
import AppFooter from './components/Footer';
import Home from './pages/Home';
import OntologyPage from './pages/OntologyPage';
import DashboardPage from './pages/DashboardPage';
import MapPage from './pages/MapPage';
import NewEventsPage from './pages/NewEventsPage'; // new import
import SettingsPage from './pages/SettingsPage';
import 'bootstrap/dist/css/bootstrap.min.css';
import AppNavbar from './components/AppNavbar';
import { Suspense } from 'react';
import { ConfigProvider } from './context/ConfigContext';
import FeedbackPage from './pages/FeedbackPage';
import MinioBrowserPage from './pages/MinioBrowserPage.tsx';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import TroubleshootingPage from './pages/TroubleshootingPage';
import DataPipelinePage from './pages/DataPipelinePage';
import MetadataPage from './pages/MetadataPage';
import DataSourcesPage from './pages/DataSourcesPage';
import ErrorBoundary from './components/ErrorBoundary';
import DebugFloatingButton from './components/DebugFloatingButton';
import LoginPage from './pages/LoginPage';
import './utils/devTools'; // Initialize dev tools

function App() {

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ConfigProvider>
          <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<div>Loading...</div>}>
            <div className="App">
              <AppNavbar />
              <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<LoginPage />} />
                <Route path="/pipeline" element={<DataPipelinePage />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/ontology" element={<OntologyPage />} />
                <Route path="/map" element={<MapPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/feedback" element={<FeedbackPage />} />
                <Route path="/minio" element={<MinioBrowserPage />} />
                <Route path="/troubleshooting" element={<TroubleshootingPage />} />
                <Route path="/metadata" element={<MetadataPage />} />
                <Route path="/data-sources" element={<DataSourcesPage />} />
                <Route path="/new-events" element={<NewEventsPage />} /> {/* new route */}
              </Routes>
              <AppFooter />
              <DebugFloatingButton />
            </div>
          </Suspense>
        </BrowserRouter>
          </AuthProvider>
        </ConfigProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
