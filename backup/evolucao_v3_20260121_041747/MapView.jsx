import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Loader2 } from 'lucide-react';

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const getMarkerIcon = (status, isCurrent) => {
    const path = "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z";
    let fillColor = "#3B82F6"; 
    if (status === 'success') fillColor = "#10B981";
    if (status === 'failed') fillColor = "#EF4444";
    if (status === 'partial') fillColor = "#F59E0B";
    if (isCurrent) fillColor = "#0F172A";

    return {
        path: path,
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 1.5,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.0 : 1.4,
        anchor: { x: 12, y: 22 },
        labelOrigin: { x: 12, y: 10 }
    };
};

export default function MapView({ 
    userPos, 
    groupedStops, 
    directionsResponse, 
    nextGroup, 
    openNav,
    isLoaded
}) {
    const [selectedMarker, setSelectedMarker] = useState(null);
    const [mapInstance, setMapInstance] = useState(null);

    if (!isLoaded) return <div className="flex h-full items-center justify-center"><Loader2 className="animate-spin"/> Carregando Mapa...</div>;

    return (
        <GoogleMap
            mapContainerStyle={mapContainerStyle}
            center={userPos || { lat: -23.55, lng: -46.63 }}
            zoom={14}
            options={mapOptions}
            onLoad={setMapInstance}
        >
            {directionsResponse && (
                <DirectionsRenderer 
                    directions={directionsResponse} 
                    options={{ suppressMarkers: true, polylineOptions: { strokeColor: "#2563EB", strokeWeight: 5 } }} 
                />
            )}
            
            {groupedStops.map((g, idx) => (
                <MarkerF 
                    key={g.id} 
                    position={{ lat: g.lat, lng: g.lng }}
                    label={{ text: String(idx + 1), color: "white", fontSize: "12px", fontWeight: "bold" }}
                    icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                    onClick={() => setSelectedMarker(g)}
                />
            ))}
            
            {userPos && (
                <MarkerF 
                    position={{ lat: userPos.lat, lng: userPos.lng }} 
                    icon={getMarkerIcon('current', true)} 
                    zIndex={1000}
                />
            )}

            {selectedMarker && (
                <InfoWindowF 
                    position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} 
                    onCloseClick={() => setSelectedMarker(null)}
                >
                    <div className="p-2 min-w-[200px]">
                        <h3 className="font-bold text-sm mb-1">Parada: {selectedMarker.mainName}</h3>
                        <p className="text-xs text-slate-500 mb-2">{selectedMarker.mainAddress}</p>
                        <button 
                            onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} 
                            className="w-full bg-blue-600 text-white py-2 rounded text-xs font-bold"
                        >
                            NAVEGAR AQUI
                        </button>
                    </div>
                </InfoWindowF>
            )}
        </GoogleMap>
    );
}
