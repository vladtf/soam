import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Container } from 'react-bootstrap';

interface Building {
  name: string;
  lat: number;
  lng: number;
}

const MapPage: React.FC = () => {
  const [buildings, setBuildings] = useState<Building[]>([]);

  useEffect(() => {
    fetch('http://localhost:8000/buildings')
      .then(res => res.json())
      .then(data => setBuildings(data))
      .catch(err => console.error("Error fetching buildings:", err));
  }, []);

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
      </MapContainer>
    </Container>
  );
};

export default MapPage;
