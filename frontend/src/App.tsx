import { Routes, Route, BrowserRouter } from 'react-router-dom';
import './App.css';
import AppFooter from './components/Footer';
import Home from './pages/Home';
import SensorDataPage from './pages/SensorDataPage';
import OntologyPage from './pages/OntologyPage';
import DashboardPage from './pages/DashboardPage';
import MapPage from './pages/MapPage';
import 'bootstrap/dist/css/bootstrap.min.css';
import AppNavbar from './components/AppNavbar';
import { Suspense } from 'react';
import { ConfigProvider } from './context/ConfigContext';

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
            </Routes>
            <AppFooter />
          </div>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  );
}

export default App;
