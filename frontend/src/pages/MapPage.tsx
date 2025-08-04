import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Container } from 'react-bootstrap';
import NewBuildingModal from '../components/NewBuildingModal';
import { postNewBuilding, fetchBuildings } from '../api/backendRequests';
import { Building } from '../models/Building';

// Fix Leaflet default marker icons issue in React
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});



const MapPage: React.FC = () => {
  const [buildings, setBuildings] = useState<Building[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [selectedLat, setSelectedLat] = useState(0);
  const [selectedLng, setSelectedLng] = useState(0);
  const [selectedBuilding, setSelectedBuilding] = useState('');
  const [address, setAddress] = useState('');
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');

  useEffect(() => {
    loadBuildings();
  }, []);

  const loadBuildings = async () => {
    try {
      const data = await fetchBuildings();
      setBuildings(data);
    } catch (err) {
      console.error("Error fetching buildings:", err);
    }
  };

  const handleAddBuilding = async (newBuilding: Building) => {
    await postNewBuilding(newBuilding);
    await loadBuildings(); // Refetch buildings after adding new building
    setShowModal(false);
  };


  // Inner component to handle map click events.
  const MapClickHandler: React.FC<{ onClick: (lat: number, lng: number) => void }> = ({ onClick }) => {
    useMapEvents({
      click(e) {
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
      console.error("Error fetching address:", error);
    }
  };

  const handleMapClick = async (lat: number, lng: number) => {
    setSelectedLat(lat);
    setSelectedLng(lng);
    await fetchAddress(lat, lng);
    setShowModal(true);
  };


  return (
    <Container className="mt-3">
      <h1>Building Map</h1>
      <MapContainer center={[44.436170, 26.102765]} zoom={13} style={{ height: '80vh', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="http://osm.org/copyright">OSM</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {buildings.map((b, i) => (
          <Marker key={i} position={[b.lat, b.lng]}>
            <Popup>{b.name}</Popup>
          </Marker>
        ))}
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
