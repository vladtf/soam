import React, { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Button, ButtonGroup, Container, Modal } from 'react-bootstrap';
import NewBuildingModal from '../components/NewBuildingModal';
import { postNewBuilding, fetchBuildings, deleteBuilding } from '../api/backendRequests';
import { Building } from '../models/Building';
import PageHeader from '../components/PageHeader';
import { useTheme } from '../context/ThemeContext';
import { toast } from 'react-toastify';
import { useError } from '../context/ErrorContext';
import { reportClientError } from '../errors';

type MapClickEvent = { latlng: { lat: number; lng: number } };

// Fix Leaflet default marker icons issue in React
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});



type BaseMapMode = 'auto' | 'light' | 'dark';

function getInitialBasemapMode(): BaseMapMode {
  try {
    const v = localStorage.getItem('basemapMode');
    if (v === 'auto' || v === 'light' || v === 'dark') return v;
  } catch {
    // ignore
  }
  return 'auto';
}

function basemapFor(mode: BaseMapMode, theme: 'light' | 'dark') {
  const effective = mode === 'auto' ? theme : mode;
  if (effective === 'dark') {
    return {
      // CartoDB Dark Matter
      url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    };
  }
  return {
    // Standard OSM
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="http://osm.org/copyright">OSM</a> contributors',
  };
}

const MapPage: React.FC = () => {
  const { theme } = useTheme();
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [selectedLat, setSelectedLat] = useState(0);
  const [selectedLng, setSelectedLng] = useState(0);
  const [selectedBuilding, setSelectedBuilding] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');
  const [basemapMode, setBasemapMode] = useState<BaseMapMode>(getInitialBasemapMode);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirmTarget, setConfirmTarget] = useState<{ name: string; lat: number; lng: number } | null>(null);
  const [addrCache, setAddrCache] = useState<Record<string, string>>({});

  const tile = useMemo(() => basemapFor(basemapMode, theme), [basemapMode, theme]);

  useEffect(() => {
    loadBuildings();
  }, []);

  const { setError } = useError();

  const loadBuildings = async () => {
    try {
      const data = await fetchBuildings();
      setBuildings(data);
    } catch (err) {
      setError(err);
      reportClientError({ message: String(err), severity: 'error', component: 'MapPage', context: 'loadBuildings' }).catch(() => {});
    }
  };

  const handleAddBuilding = async (newBuilding: Building) => {
    await postNewBuilding(newBuilding);
    await loadBuildings(); // Refetch buildings after adding new building
    setShowModal(false);
    toast.success('Building added');
  };

  const handleDeleteBuilding = async (name: string, lat: number, lng: number) => {
    try {
      await deleteBuilding(name, lat, lng);
      await loadBuildings();
      toast.success('Building deleted');
    } catch (err) {
      setError(err);
      reportClientError({ message: String(err), severity: 'error', component: 'MapPage', context: 'deleteBuilding' }).catch(() => {});
      toast.error(`Failed to delete building: ${String(err)}`);
    }
  };

  const openConfirmDelete = (name: string, lat: number, lng: number) => {
    setConfirmTarget({ name, lat, lng });
    setConfirmOpen(true);
  };

  const confirmDelete = async () => {
    if (!confirmTarget) return;
    await handleDeleteBuilding(confirmTarget.name, confirmTarget.lat, confirmTarget.lng);
    setConfirmOpen(false);
    setConfirmTarget(null);
  };

  const keyFor = (lat: number, lng: number) => `${lat.toFixed(6)},${lng.toFixed(6)}`;

  const reverseGeocode = async (lat: number, lng: number) => {
    const key = keyFor(lat, lng);
    if (addrCache[key]) return; // cached
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`);
      const data = await res.json();
      const addr = data?.display_name || [data?.address?.road, data?.address?.city || data?.address?.town || data?.address?.village, data?.address?.country]
        .filter(Boolean)
        .join(', ');
      setAddrCache(prev => ({ ...prev, [key]: addr || key }));
    } catch {
      setAddrCache(prev => ({ ...prev, [key]: key }));
    }
  };


  // Inner component to handle map click events.
  const MapClickHandler: React.FC<{ onClick: (lat: number, lng: number) => void }> = ({ onClick }) => {
    useMapEvents({
      click(e: MapClickEvent) {
        onClick(e.latlng.lat, e.latlng.lng);
      }
    });
    return null;
  };

  const fetchAddress = async (lat: number, lng: number) => {
    try {
      const res = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`);
      const data = await res.json();
      // Update state with the available address info (adjust properties as needed)
      setSelectedBuilding(data.name || '');
      setAddress(data.address.road || '');
      setCity(data.address.city || data.address.town || data.address.village || '');
      setCountry(data.address.country || '');
    } catch (error) {
      setError(error);
      reportClientError({ message: String(error), severity: 'warn', component: 'MapPage', context: 'fetchAddress' }).catch(() => {});
    }
  };

  const handleMapClick = async (lat: number, lng: number) => {
    setSelectedLat(lat);
    setSelectedLng(lng);
    await fetchAddress(lat, lng);
    setShowModal(true);
  };


  return (
  <Container className="pt-3 pb-4">
      <PageHeader
        title="Building Map"
        right={
      <ButtonGroup size="sm" aria-label="Basemap mode">
            {(['auto', 'light', 'dark'] as BaseMapMode[]).map((m) => (
              <Button
                key={m}
                variant={basemapMode === m ? 'primary' : 'outline-secondary'}
                onClick={() => {
                  setBasemapMode(m);
                  try { localStorage.setItem('basemapMode', m); } catch { /* ignore */ }
                }}
        title={`Basemap: ${m}`}
        aria-pressed={basemapMode === m}
        aria-label={`Basemap ${m}${basemapMode === m ? ' (selected)' : ''}`}
              >
                {m[0].toUpperCase() + m.slice(1)}
              </Button>
            ))}
          </ButtonGroup>
        }
      />
      <MapContainer center={[44.436170, 26.102765]} zoom={13} style={{ height: '80vh', width: '100%' }}>
        <TileLayer attribution={tile.attribution} url={tile.url} />
        {buildings.map((b, i) => (
          <Marker
            key={`${b.name}-${b.lat}-${b.lng}-${i}`}
            position={[b.lat, b.lng]}
            eventHandlers={{ click: () => reverseGeocode(b.lat, b.lng) }}
          >
            <Popup>
              <div className="d-flex flex-column gap-2">
                <div>
                  <strong>{b.name}</strong>
                </div>
                <small className="text-muted">
                  {addrCache[keyFor(b.lat, b.lng)] || `${b.lat.toFixed(6)}, ${b.lng.toFixed(6)}`}
                </small>
                <div>
                  <Button size="sm" variant="outline-danger" onClick={() => openConfirmDelete(b.name, b.lat, b.lng)}>
                    Delete
                  </Button>
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

      {/* Confirm Deletion Modal */}
      <Modal show={confirmOpen} onHide={() => setConfirmOpen(false)}>
        <Modal.Header closeButton>
          <Modal.Title>Delete Building</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {confirmTarget ? (
            <div>
              Are you sure you want to delete
              {' '}<strong>{confirmTarget.name}</strong>?
              <div className="mt-2 text-muted">
                {addrCache[keyFor(confirmTarget.lat, confirmTarget.lng)] || `${confirmTarget.lat.toFixed(6)}, ${confirmTarget.lng.toFixed(6)}`}
              </div>
            </div>
          ) : null}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>Cancel</Button>
          <Button variant="danger" onClick={confirmDelete}>Delete</Button>
        </Modal.Footer>
      </Modal>
        <MapClickHandler onClick={handleMapClick} />
      </MapContainer>
      <NewBuildingModal
        show={showModal}
        lat={selectedLat}
        lng={selectedLng}
        selectedBuilding={selectedBuilding}
        selectedAddress={address}
        selectedCity={city}
        selectedCountry={country}
        handleClose={() => setShowModal(false)}
        onSubmit={handleAddBuilding}
      />
    </Container>
  );
};

export default MapPage;
