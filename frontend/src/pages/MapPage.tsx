import React from 'react';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Container } from 'react-bootstrap';

// Mock sensor data with coordinates and labels
const sensors = [
    { id: 1, name: "Sensor A", lat: 44.4268, lng: 26.1025 },
    { id: 2, name: "Sensor B", lat: 44.4278, lng: 26.1035 },
    { id: 3, name: "Sensor C", lat: 44.4288, lng: 26.1045 }
  ];

const MapPage: React.FC = () => {
  return (
    <Container className="mt-3">
      <h1>Sensor Map</h1>
      <MapContainer center={[51.505, -0.09]} zoom={13} style={{ height: '80vh', width: '100%' }}>
        <TileLayer
          attribution='&copy; <a href="http://osm.org/copyright">OSM</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {sensors.map(sensor => (
          <Marker key={sensor.id} position={[sensor.lat, sensor.lng]}>
            <Popup>{sensor.name}</Popup>
          </Marker>
        ))}
      </MapContainer>
    </Container>
  );
};

export default MapPage;
