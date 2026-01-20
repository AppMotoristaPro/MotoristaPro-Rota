import os
import shutil
import subprocess
import sys
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

# --- CONTEÚDO DOS ARQUIVOS ---

files_content = {}

# 1. src/index.css (Adicionando estilos para os marcadores numéricos e animações)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  -webkit-font-smoothing: antialiased;
  background-color: #f8fafc;
}

/* --- MARCADORES PERSONALIZADOS (CSS PURA PARA PERFORMANCE) --- */
.custom-pin {
  background-color: #3b82f6;
  border: 2px solid white;
  border-radius: 50%;
  color: white;
  font-weight: bold;
  font-size: 12px;
  display: flex !important;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 6px rgba(0,0,0,0.3);
  transition: transform 0.2s;
}

.pin-success { background-color: #22c55e; } /* Verde */
.pin-failed { background-color: #ef4444; }  /* Vermelho */
.pin-active { 
  background-color: #eab308; /* Amarelo/Dourado */
  transform: scale(1.2);
  border: 3px solid white;
  z-index: 1000 !important;
  box-shadow: 0 0 15px rgba(234, 179, 8, 0.6);
}

/* Animação de Pulso para o GPS do Usuário */
.user-gps-marker {
  background-color: #3b82f6;
  border: 2px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
  animation: pulse-blue 2s infinite;
}

@keyframes pulse-blue {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 15px rgba(59, 130, 246, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}

/* Container de Navegação estilo Google Maps */
.nav-panel-top {
  background: #1e293b;
  color: white;
}
'''

# 2. src/App.jsx (Lógica completa refeita para GPS Real e Performance)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Upload, Map as MapIcon, Navigation, List, Truck, Check, AlertTriangle, ChevronRight, MapPin, Clock, Gauge } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import L from 'leaflet';
import 'leaflet-routing-machine';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- CONFIGURAÇÃO DE ÍCONES (DIVICONS PARA PERFORMANCE) ---
const createNumberedIcon = (number, status, isActive) => {
  let className = 'custom-pin';
  if (status === 'success') className += ' pin-success';
  else if (status === 'failed') className += ' pin-failed';
  else if (isActive) className += ' pin-active';

  return L.divIcon({
    className: className,
    html: `<span>${status === 'success' ? '✓' : number}</span>`,
    iconSize: isActive ? [40, 40] : [30, 30],
    iconAnchor: isActive ? [20, 20] : [15, 15]
  });
};

const userIcon = L.divIcon({
  className: 'user-gps-marker',
  iconSize: [20, 20],
  iconAnchor: [10, 10]
});

// --- CÁLCULO DE MÉTRICAS (Distância e Tempo) ---
const calculateMetrics = (stops, userPos) => {
  if (!stops || stops.length === 0) return { km: 0, time: 0 };
  
  let totalKm = 0;
  let currentLat = userPos?.lat || stops[0].lat;
  let currentLng = userPos?.lng || stops[0].lng;

  // Fórmula de Haversine
  const haversine = (lat1, lon1, lat2, lon2) => {
    const R = 6371; 
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon/2) * Math.sin(dLon/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)); 
    return R * c;
  };

  stops.forEach(stop => {
    if (stop.status === 'pending') {
      const dist = haversine(currentLat, currentLng, stop.lat, stop.lng);
      totalKm += dist;
      currentLat = stop.lat;
      currentLng = stop.lng;
    }
  });

  // Estimativa: Distância Real (x1.4 curvatura) / 25km/h + 5min por parada
  const realKm = totalKm * 1.4;
  const pendingStops = stops.filter(s => s.status === 'pending').length;
  const travelTimeHours = realKm / 25;
  const serviceTimeHours = (pendingStops * 5) / 60; // 5 min por parada
  const totalHours = travelTimeHours + serviceTimeHours;

  // Formatação
  const hours = Math.floor(totalHours);
  const minutes = Math.round((totalHours - hours) * 60);

  return {
    km: realKm.toFixed(1),
    timeStr: `${hours}h ${minutes}min`
  };
};

// --- COMPONENTE: LINHA DE ROTA (Apenas para o próximo ponto para evitar lag) ---
function ActiveRouteLine({ start, end }) {
  const map = useMap();
  const routingControlRef = useRef(null);

  useEffect(() => {
    if (!map || !start || !end) return;

    // Limpar rota anterior
    if (routingControlRef.current) {
      try { map.removeControl(routingControlRef.current); } catch(e) {}
    }

    const plan = L.Routing.plan(
      [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      { createMarker: () => null, addWaypoints: false }
    );

    routingControlRef.current = L.Routing.control({
      waypoints: [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      plan: plan,
      lineOptions: { styles: [{ color: '#3b82f6', weight: 6, opacity: 0.8 }] },
      routeWhileDragging: false,
      show: false,
      addWaypoints: false,
      fitSelectedRoutes: false // NÃO dar zoom automático toda hora
    }).addTo(map);

    return () => {
      if (routingControlRef.current) {
        try { map.removeControl(routingControlRef.current); } catch(e) {}
      }
    };
  }, [map, start, end]);

  return null;
}

// --- COMPONENTE: AUTO-NAVIGATE (Seguir o usuário) ---
function AutoNavigate({ center, enable }) {
  const map = useMap();
  useEffect(() => {
    if (enable && center) {
      map.flyTo(center, 18, { animate: true, duration: 1 }); // Zoom 18 = Estilo GPS
    }
  }, [center, enable, map]);
  return null;
}

export default function App() {
  const [view, setView] = useState('import');
  const [stops, setStops] = useState([]);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  const [userLocation, setUserLocation] = useState(null);
  const [gpsLoading, setGpsLoading] = useState(true);
  const [metrics, setMetrics] = useState({ km: 0, timeStr: '0h 0min' });

  // 1. GPS REAL OBRIGATÓRIO
  useEffect(() => {
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const newPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setUserLocation(newPos);
        setGpsLoading(false);
      },
      (err) => {
        console.error("Erro GPS", err);
        alert("Precisamos do GPS para funcionar. Ative a localização.");
      },
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  // Recalcular métricas quando as paradas mudam
  useEffect(() => {
    if (userLocation && stops.length > 0) {
      setMetrics(calculateMetrics(stops, userLocation));
    }
  }, [stops, userLocation]);

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const processFile = (dataStr, isBinary = false) => {
      let data = [];
      if (!isBinary) {
        const result = Papa.parse(dataStr, { header: true, skipEmptyLines: true });
        data = normalizeData(result.data);
      } else {
        const wb = XLSX.read(dataStr, { type: 'binary' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        data = normalizeData(XLSX.utils.sheet_to_json(ws));
      }
      if (data.length > 0) {
        setStops(data.map(d => ({ ...d, status: 'pending' }))); 
        setView('list');
      } else {
        alert("Erro: Planilha inválida.");
      }
    };

    const reader = new FileReader();
    if (file.name.endsWith('.csv')) {
      reader.onload = (evt) => processFile(evt.target.result);
      reader.readAsText(file);
    } else {
      reader.onload = (evt) => processFile(evt.target.result, true);
      reader.readAsBinaryString(file);
    }
  };

  const normalizeData = (rawData) => {
    return rawData.map((row, index) => {
      const k = Object.keys(row).reduce((acc, key) => { acc[key.toLowerCase().trim()] = row[key]; return acc; }, {});
      const lat = parseFloat(k['latitude'] || k['lat'] || 0);
      const lng = parseFloat(k['longitude'] || k['long'] || k['lng'] || 0);
      const name = k['stop'] || k['nome'] || k['cliente'] || `Parada ${index + 1}`;
      const address = k['destination address'] || k['endereço'] || k['endereco'] || '---';
      return { id: index, name, address, lat, lng };
    }).filter(i => i.lat !== 0 && i.lng !== 0);
  };

  const optimizeRoute = () => {
    if (!userLocation) {
        alert("Aguardando sinal de GPS para otimizar...");
        return;
    }
    
    // Algoritmo Vizinho Mais Próximo
    let currentPos = userLocation;
    let pendingStops = stops.filter(s => s.status === 'pending');
    let finishedStops = stops.filter(s => s.status !== 'pending');
    let optimized = [];

    while (pendingStops.length > 0) {
      let nearestIndex = -1;
      let minDist = Infinity;

      for (let i = 0; i < pendingStops.length; i++) {
        // Distancia Euclideana simples para velocidade (Haversine é pesado no loop)
        const d = Math.pow(pendingStops[i].lat - currentPos.lat, 2) + Math.pow(pendingStops[i].lng - currentPos.lng, 2);
        if (d < minDist) {
          minDist = d;
          nearestIndex = i;
        }
      }
      optimized.push(pendingStops[nearestIndex]);
      currentPos = pendingStops[nearestIndex];
      pendingStops.splice(nearestIndex, 1);
    }

    setStops([...finishedStops, ...optimized]);
    setCurrentStopIndex(finishedStops.length); // Aponta para o primeiro pendente
    setView('navigation');
  };

  const handleDelivery = (status) => {
    const newStops = [...stops];
    newStops[currentStopIndex].status = status;
    setStops(newStops);
    
    if (currentStopIndex < stops.length - 1) {
      setCurrentStopIndex(prev => prev + 1);
    } else {
      alert("Rota Finalizada!");
      setView('list');
    }
  };

  const openWaze = () => {
    const stop = stops[currentStopIndex];
    window.open(`waze://?ll=${stop.lat},${stop.lng}&navigate=yes`, '_system');
  };

  // Se GPS estiver carregando, bloqueia tudo
  if (gpsLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-blue-600 text-white flex-col">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mb-4"></div>
        <h2 className="text-xl font-bold">Buscando GPS...</h2>
        <p className="text-sm opacity-80 mt-2">Por favor, aguarde a localização precisa.</p>
      </div>
    );
  }

  const currentStop = stops[currentStopIndex];

  return (
    <div className="flex flex-col h-screen bg-slate-50 font-sans text-slate-800">
      
      {/* HEADER DE MÉTRICAS (VISÍVEL NA LISTA E NAV) */}
      {view !== 'import' && (
        <div className="bg-white px-4 py-3 shadow-sm border-b flex justify-between items-center z-20">
          <div className="flex flex-col">
            <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Tempo Est.</span>
            <div className="flex items-center gap-1 font-bold text-slate-800">
                <Clock size={14} className="text-blue-500"/> {metrics.timeStr}
            </div>
          </div>
          <div className="flex flex-col text-right">
            <span className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Distância</span>
            <div className="flex items-center justify-end gap-1 font-bold text-slate-800">
                <Gauge size={14} className="text-green-500"/> {metrics.km} km
            </div>
          </div>
        </div>
      )}

      <main className="flex-1 relative overflow-hidden">
        
        {view === 'import' && (
          <div className="h-full flex flex-col items-center justify-center p-6">
            <div className="bg-white p-8 rounded-2xl shadow-xl text-center w-full max-w-sm">
              <Truck size={48} className="mx-auto text-blue-600 mb-4" />
              <h2 className="text-xl font-bold mb-2">MotoristaPro</h2>
              <p className="text-gray-400 text-sm mb-6">Localização detectada. Importe sua rota.</p>
              <label className="block w-full cursor-pointer">
                <div className="w-full py-4 bg-blue-50 text-blue-700 font-bold rounded-xl border border-blue-100 text-sm">
                  Selecionar Planilha
                </div>
                <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx, .xls" className="hidden" />
              </label>
            </div>
          </div>
        )}

        {view === 'list' && (
          <div className="h-full flex flex-col">
             <div className="p-4">
              <button onClick={optimizeRoute} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2">
                <Navigation size={20} /> Iniciar Navegação
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-2 pb-20">
              {stops.map((stop, idx) => (
                <div key={idx} className={`p-4 mb-2 bg-white rounded-xl border border-gray-100 flex items-center gap-3 ${stop.status !== 'pending' ? 'opacity-50' : ''}`}>
                  <div className="font-bold text-gray-400 text-sm">#{idx + 1}</div>
                  <div className="flex-1">
                    <h3 className="font-bold text-sm">{stop.name}</h3>
                    <p className="text-xs text-gray-500">{stop.address}</p>
                  </div>
                  {stop.status === 'success' && <Check className="text-green-500" size={16} />}
                </div>
              ))}
            </div>
          </div>
        )}

        {view === 'navigation' && (
          <div className="h-full w-full relative">
            {/* PAINEL SUPERIOR ESTILO GOOGLE MAPS */}
            {currentStop && (
                <div className="absolute top-0 left-0 right-0 nav-panel-top p-4 z-[1000] shadow-lg">
                    <div className="flex items-start gap-3">
                        <div className="bg-green-500 mt-1 w-8 h-8 rounded-full flex items-center justify-center font-bold text-white shrink-0">
                            {currentStopIndex + 1}
                        </div>
                        <div className="flex-1 text-white">
                            <h2 className="font-bold text-lg leading-tight">{currentStop.name}</h2>
                            <p className="text-slate-300 text-sm mt-1">{currentStop.address}</p>
                        </div>
                    </div>
                </div>
            )}

            <MapContainer center={[userLocation.lat, userLocation.lng]} zoom={18} style={{ height: '100%', width: '100%' }} zoomControl={false}>
              <TileLayer url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}" attribution="Google" />
              
              {/* Modo Seguir Usuário */}
              <AutoNavigate center={userLocation} enable={true} />

              {/* Rota Ativa (Apenas para o próximo) */}
              {currentStop && <ActiveRouteLine start={userLocation} end={currentStop} />}

              {/* Marcadores Otimizados */}
              {stops.map((stop, idx) => {
                 // Só mostra marcadores pendentes ou o atual para não poluir
                 if (stop.status !== 'pending' && idx !== currentStopIndex) return null;
                 return (
                    <Marker 
                        key={idx} 
                        position={[stop.lat, stop.lng]} 
                        icon={createNumberedIcon(idx + 1, stop.status, idx === currentStopIndex)}
                    >
                        {/* Removemos Popup automático para limpar a visão */}
                    </Marker>
                 )
              })}

              <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon} />
            </MapContainer>

            {/* CONTROLES INFERIORES */}
            <div className="absolute bottom-0 left-0 right-0 bg-white p-4 rounded-t-3xl shadow-2xl z-[1000]">
                <div className="flex gap-3 mb-3">
                     <button onClick={openWaze} className="flex-1 bg-gray-100 text-slate-700 py-3 rounded-xl font-bold text-xs flex items-center justify-center gap-2">
                        <Navigation size={14}/> Navegador Externo
                     </button>
                </div>
                <div className="flex gap-3 h-16">
                    <button onClick={() => handleDelivery('failed')} className="w-1/3 bg-orange-100 text-orange-700 rounded-xl font-bold flex flex-col items-center justify-center">
                        <AlertTriangle size={20} className="mb-1"/>
                        <span className="text-[10px]">Ocorrência</span>
                    </button>
                    <button onClick={() => handleDelivery('success')} className="w-2/3 bg-green-600 text-white rounded-xl font-bold flex flex-col items-center justify-center shadow-green-200 shadow-lg">
                        <Check size={24} className="mb-1"/>
                        <span className="text-xs">ENTREGUE</span>
                    </button>
                </div>
            </div>
          </div>
        )}

      </main>

      {view !== 'navigation' && (
        <nav className="bg-white border-t py-3 flex justify-around pb-safe">
            <button onClick={() => setView('import')} className="text-gray-400"><Upload/></button>
            <button onClick={() => setView('list')} className="text-blue-600"><List/></button>
        </nav>
      )}
    </div>
  );
}'''

# --- FUNÇÕES AUXILIARES ---

def backup_files():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(BACKUP_ROOT, timestamp)
    print(f"📦 Backup: {backup_dir}")
    os.makedirs(backup_dir, exist_ok=True)
    
    for filename in files_content.keys():
        if os.path.exists(filename):
            dest = os.path.join(backup_dir, filename)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(filename, dest)

def update_files():
    print("\n📝 Atualizando V5...")
    for filename, content in files_content.items():
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ {filename}")

def run_command(command, msg):
    try:
        subprocess.run(command, shell=True, check=True)
        return True
    except:
        print(f"❌ {msg}")
        return False

def main():
    print(f"🚀 ATUALIZAÇÃO V5 - PERFORMANCE & GPS - {APP_NAME}")
    backup_files()
    update_files()
    
    print("\n☁️ GitHub Push...")
    run_command("git add .", "Add failed")
    run_command('git commit -m "feat: V5 High Performance, Real GPS, Metrics & Styles"', "Commit failed")
    if run_command("git push origin main", "Push failed"):
        print("\n✅ SUCESSO! Código enviado.")
    
    try: os.remove(__file__) 
    except: pass

if __name__ == "__main__":
    main()


