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

function App() {

  return (
    <ConfigProvider>
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
              <Route path="/new-events" element={<NewEventsPage />} /> {/* new route */}
            </Routes>
            <AppFooter />
          </div>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
