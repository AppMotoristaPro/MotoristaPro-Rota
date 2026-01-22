import React, { useState } from 'react';
import { GoogleMap, MarkerF, InfoWindowF, DirectionsRenderer } from '@react-google-maps/api';
import { Loader2, Navigation, Package, MapPin, XCircle, CheckCircle, Layers, Edit3 } from 'lucide-react';

const mapContainerStyle = { width: '100%', height: '100%' };
const mapOptions = {
    disableDefaultUI: true,
    zoomControl: false,
    clickableIcons: false
};

const getMarkerIcon = (status, isCurrent, isReordering, reorderIndex) => {
    let fillColor = "#3B82F6"; 
    let scale = 1.6;
    let strokeColor = "#FFFFFF";

    if (isReordering) {
        if (reorderIndex !== -1) {
            fillColor = "#10B981"; 
            scale = 1.8;
            strokeColor = "#000000";
        } else {
            fillColor = "#94A3B8"; 
        }
    } else {
        if (status === 'success') fillColor = "#10B981";
        if (status === 'failed') fillColor = "#EF4444";
        if (status === 'partial') fillColor = "#F59E0B"; 
        if (isCurrent) {
            fillColor = "#0F172A"; 
            scale = 2.2;
        }
    }

    return {
        path: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z",
        fillColor: fillColor,
        fillOpacity: 1,
        strokeWeight: 2,
        strokeColor: strokeColor,
        scale: scale,
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
    isLoaded,
    setStatus,
    setAllStatus,
    isReordering, 
    reorderList, 
    onMarkerClick,
    onStartReorder
}) {
    const [selectedMarker, setSelectedMarker] = useState(null);
    const [mapInstance, setMapInstance] = useState(null);

    if (!isLoaded) return <div className="flex h-full items-center justify-center bg-slate-100"><Loader2 className="animate-spin text-slate-400"/></div>;

    const handleMarkerClick = (group) => {
        if (isReordering) {
            onMarkerClick(group.id);
        } else {
            setSelectedMarker(group);
        }
    };

    return (
        <div className="relative w-full h-full">
            <GoogleMap
                mapContainerStyle={mapContainerStyle}
                center={userPos || { lat: -23.55, lng: -46.63 }}
                zoom={15}
                options={mapOptions}
                onLoad={setMapInstance}
            >
                {!isReordering && directionsResponse && (
                    <DirectionsRenderer 
                        directions={directionsResponse} 
                        options={{ 
                            suppressMarkers: true, 
                            polylineOptions: { strokeColor: "#2563EB", strokeWeight: 6, strokeOpacity: 0.8 } 
                        }} 
                    />
                )}
                
                {groupedStops.map((g, idx) => {
                    let labelText = null; 

                    if (isReordering) {
                        const newIndex = reorderList.indexOf(g.id);
                        if (newIndex !== -1) {
                            labelText = String(newIndex + 1); 
                        }
                    } else {
                        if (g.displayOrder !== null && g.displayOrder !== undefined) {
                            labelText = String(g.displayOrder);
                        }
                    }

                    return (
                        <MarkerF 
                            key={g.id} 
                            position={{ lat: g.lat, lng: g.lng }}
                            label={labelText ? { text: labelText, color: "white", fontSize: "11px", fontWeight: "bold" } : null}
                            icon={getMarkerIcon(
                                g.status, 
                                !isReordering && nextGroup && g.id === nextGroup.id,
                                isReordering,
                                isReordering ? reorderList.indexOf(g.id) : -1
                            )}
                            onClick={() => handleMarkerClick(g)}
                            zIndex={10}
                        />
                    )
                })}
                
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

                {selectedMarker && !isReordering && (
                    <InfoWindowF 
                        position={{ lat: selectedMarker.lat, lng: selectedMarker.lng }} 
                        onCloseClick={() => setSelectedMarker(null)}
                    >
                        <div className="p-1 min-w-[240px] max-w-[260px]">
                            <div className="flex items-start gap-2 mb-2 border-b border-gray-100 pb-2">
                                <div className="bg-slate-100 p-1.5 rounded-full mt-0.5"><MapPin size={16} className="text-slate-600"/></div>
                                <div>
                                    <h3 className="font-bold text-sm text-slate-800 leading-tight">
                                        {selectedMarker.displayOrder ? `Parada ${selectedMarker.displayOrder}` : 'Sem ID Planilha'}
                                    </h3>
                                    <p className="text-[11px] text-slate-500 mt-0.5 leading-snug">{selectedMarker.mainName}</p>
                                </div>
                            </div>
                            
                            {selectedMarker.items.filter(i => i.status === 'pending').length > 1 && (
                                <button 
                                    onClick={() => {
                                        setAllStatus(selectedMarker.items, 'success');
                                        setSelectedMarker(null);
                                    }}
                                    className="w-full mb-2 bg-green-100 text-green-700 py-1.5 rounded border border-green-200 text-[10px] font-bold flex items-center justify-center gap-2"
                                >
                                    <Layers size={12}/> ENTREGAR TODOS ({selectedMarker.items.filter(i => i.status === 'pending').length})
                                </button>
                            )}

                            <div className="max-h-[150px] overflow-y-auto mb-2 space-y-2">
                                {selectedMarker.items.map((item) => (
                                    <div key={item.id} className="bg-slate-50 p-2 rounded border border-slate-100">
                                        <p className="text-[10px] font-bold text-slate-700 mb-1 truncate">{item.address}</p>
                                        
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-1">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 bg-white border border-red-200 text-red-500 py-1 rounded text-[10px] font-bold flex items-center justify-center gap-1"><XCircle size={10}/> Ocorrência</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 bg-green-500 text-white py-1 rounded text-[10px] font-bold flex items-center justify-center gap-1 shadow-sm"><CheckCircle size={10}/> Entregue</button>
                                            </div>
                                        ) : (
                                            <span className={`text-[10px] font-bold px-2 py-0.5 rounded w-full block text-center ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>{item.status === 'success' ? 'ENTREGUE' : 'OCORRÊNCIA'}</span>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <button onClick={() => openNav(selectedMarker.lat, selectedMarker.lng)} className="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg text-xs font-bold uppercase tracking-wide flex items-center justify-center gap-2 shadow-sm">
                                <Navigation size={14}/> Navegar
                            </button>
                        </div>
                    </InfoWindowF>
                )}
            </GoogleMap>

            {/* ITEM 3: BOTÃO EDITAR NO TOPO DIREITO DO MAPA */}
            {!isReordering && (
                <div className="absolute top-4 right-4 z-50">
                    <button 
                        onClick={onStartReorder}
                        className="bg-white text-slate-700 p-3 rounded-full shadow-lg border border-slate-200 flex items-center justify-center active:scale-95 transition"
                    >
                        <Edit3 size={20} />
                    </button>
                </div>
            )}
        </div>
    );
}
