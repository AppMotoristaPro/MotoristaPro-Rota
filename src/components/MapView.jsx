import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Loader2, Navigation, Package, MapPin } from 'lucide-react';

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const getMarkerIcon = (status, isCurrent) => {
    let fillColor = "#3B82F6"; // Azul
    if (status === 'success') fillColor = "#10B981"; // Verde
    if (status === 'failed') fillColor = "#EF4444"; // Vermelho
    if (isCurrent) fillColor = "#0F172A"; // Preto (Atual)

    return {
        path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z",
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: "#FFFFFF",
        scale: isCurrent ? 2.2 : 1.6,
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

    if (!isLoaded) return <div className="flex h-full items-center justify-center bg-slate-100"><Loader2 className="animate-spin text-slate-400"/></div>;

    return (
        <GoogleMap
            mapContainerStyle={mapContainerStyle}
            center={userPos || { lat: -23.55, lng: -46.63 }}
            zoom={15}
            options={mapOptions}
            onLoad={setMapInstance}
        >
            {directionsResponse && (
                <DirectionsRenderer 
                    directions={directionsResponse} 
                    options={{ 
                        suppressMarkers: true, 
                        polylineOptions: { strokeColor: "#2563EB", strokeWeight: 6, strokeOpacity: 0.8 } 
                    }} 
                />
            )}
            
            {groupedStops.map((g, idx) => (
                <MarkerF 
                    key={g.id} 
                    position={{ lat: g.lat, lng: g.lng }}
                    label={{ text: String(idx + 1), color: "white", fontSize: "11px", fontWeight: "bold" }}
                    icon={getMarkerIcon(g.status, nextGroup && g.id === nextGroup.id)}
                    onClick={() => setSelectedMarker(g)}
                    zIndex={nextGroup && g.id === nextGroup.id ? 1000 : 1}
                />
            ))}
            
            {userPos && (
                <MarkerF 
                    position={{ lat: userPos.lat, lng: userPos.lng }} 
                    icon={{
                        path: window.google.maps.SymbolPath.CIRCLE,
                        scale: 8,
                        fillColor: "#3B82F6",
                        fillOpacity: 1,
                        strokeWeight: 3,
                        strokeColor: "white",
                    }}
                    zIndex={2000}
                />
            )}

            {selectedMarker && (
                <InfoWindowF 
                    position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} 
                    onCloseClick={() => setSelectedMarker(null)}
                >
                    <div className="p-1 min-w-[220px]">
                        <div className="flex items-start gap-2 mb-2 border-b border-gray-100 pb-2">
                            <div className="bg-slate-100 p-1.5 rounded-full mt-0.5"><MapPin size={16} className="text-slate-600"/></div>
                            <div>
                                <h3 className="font-bold text-sm text-slate-800 leading-tight">Parada: {selectedMarker.mainName}</h3>
                                <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{selectedMarker.mainAddress}</p>
                            </div>
                        </div>
                        
                        <div className="bg-blue-50 text-blue-700 px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 mb-3 w-fit">
                            <Package size={14}/> {selectedMarker.items.length} pacotes aqui
                        </div>

                        <button 
                            onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} 
                            className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2.5 rounded-lg text-xs font-bold uppercase tracking-wide flex items-center justify-center gap-2 shadow-sm active:scale-95 transition-all"
                        >
                            <Navigation size={14}/> Navegar
                        </button>
                    </div>
                </InfoWindowF>
            )}
        </GoogleMap>
    );
}
