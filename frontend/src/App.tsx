import { Routes, Route, BrowserRouter } from 'react-router-dom';
import './App.css';
import AppFooter from './components/Footer';
import Home from './pages/Home';
import SensorDataPage from './pages/SensorDataPage';
import OntologyPage from './pages/OntologyPage';
import DashboardPage from './pages/DashboardPage';
import MapPage from './pages/MapPage';
import NewEventsPage from './pages/NewEventsPage'; // new import
import 'bootstrap/dist/css/bootstrap.min.css';
import AppNavbar from './components/AppNavbar';
import { Suspense } from 'react';
import { ConfigProvider } from './context/ConfigContext';
import FeedbackPage from './pages/FeedbackPage';
import MinioBrowserPage from './pages/MinioBrowserPage.tsx';
import NormalizationRulesPage from './pages/NormalizationRulesPage';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './context/AuthContext';
import ComputationsPage from './pages/ComputationsPage';
import TroubleshootingPage from './pages/TroubleshootingPage';

function App() {

  return (
    <ThemeProvider>
      <ConfigProvider>
        <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<div>Loading...</div>}>
          <div className="App">
            <AppNavbar />
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/sensor-data" element={<SensorDataPage />} />
              <Route path="/ontology" element={<OntologyPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/map" element={<MapPage />} />
              <Route path="/feedback" element={<FeedbackPage />} />
              <Route path="/minio" element={<MinioBrowserPage />} />
              <Route path="/normalization" element={<NormalizationRulesPage />} />
              <Route path="/computations" element={<ComputationsPage />} />
              <Route path="/troubleshooting" element={<TroubleshootingPage />} />
              <Route path="/new-events" element={<NewEventsPage />} /> {/* new route */}
            </Routes>
            <AppFooter />
          </div>
        </Suspense>
      </BrowserRouter>
        </AuthProvider>
      </ConfigProvider>
    </ThemeProvider>
  );
}

export default App;
