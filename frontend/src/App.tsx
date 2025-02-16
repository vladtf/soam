import { Routes, Route, BrowserRouter } from 'react-router-dom';
import './App.css';
import AppFooter from './components/Footer';
import Home from './pages/Home';
import SensorDataPage from './pages/SensorDataPage';
import OntologyPage from './pages/OntologyPage';
import 'bootstrap/dist/css/bootstrap.min.css';
import AppNavbar from './components/AppNavbar';
import { Suspense } from 'react';

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div>Loading...</div>}>
        <div className="App">
          <AppNavbar />
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/sensor-data" element={<SensorDataPage />} />
            <Route path="/ontology" element={<OntologyPage />} />
          </Routes>
          <AppFooter />
        </div>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
