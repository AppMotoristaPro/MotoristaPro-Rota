import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Package, Navigation } from 'lucide-react';

export default function MapView({ userPos, groupedStops, directionsResponse, nextGroup, openNav, isLoaded }) {
    const [selected, setSelected] = useState(null);

    if (!isLoaded) return <div className="h-full flex items-center justify-center">Carregando Mapa...</div>;

    return (
        <GoogleMap
            mapContainerStyle={{ width: '100%', height: '100%' }}
            center={userPos || { lat: -23.55, lng: -46.63 }}
            zoom={14}
            options={{ disableDefaultUI: true }}
        >
            {directionsResponse && <DirectionsRenderer directions={directionsResponse} options={{ suppressMarkers: true }} />}
            
            {groupedStops.map((g, idx) => (
                <MarkerF 
                    key={g.id} 
                    position={{ lat: g.lat, lng: g.lng }}
                    onClick={() => setSelected(g)}
                    label={(!directionsResponse) ? { text: String(idx + 1), color: 'white' } : null}
                />
            ))}

            {selected && (
                <InfoWindowF position={{ lat: selected.lat, lng: selected.lng }} onCloseClick={() => setSelected(null)}>
                    <div className="p-2 min-w-[180px]">
                        <p className="font-bold text-sm">{selected.mainName}</p>
                        <div className="flex items-center gap-2 text-blue-600 font-bold my-2">
                            <Package size={14}/> {selected.items.length} volumes
                        </div>
                        <button onClick={() => openNav(selected.lat, selected.lng)} className="w-full bg-slate-900 text-white py-2 rounded text-xs flex items-center justify-center gap-2">
                            <Navigation size={12}/> NAVEGAR
                        </button>
                    </div>
                </InfoWindowF>
            )}
        </GoogleMap>
    );
}
