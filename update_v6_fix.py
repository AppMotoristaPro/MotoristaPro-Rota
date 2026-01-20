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

# 1. package.json
files_content['package.json'] = '''{
  "name": "motorista-pro-rota",
  "private": true,
  "version": "1.3.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "leaflet": "^1.9.4",
    "react-leaflet": "^4.2.1",
    "lucide-react": "^0.263.1",
    "papaparse": "^5.4.1",
    "leaflet-routing-machine": "^3.2.12",
    "xlsx": "^0.18.5",
    "@capacitor/geolocation": "^5.0.0",
    "@capacitor/core": "^5.0.0",
    "@capacitor/android": "^5.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.15",
    "@types/react-dom": "^18.2.7",
    "@vitejs/plugin-react": "^4.0.3",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.27",
    "tailwindcss": "^3.3.3",
    "vite": "^4.4.5",
    "@capacitor/cli": "^5.0.0"
  }
}'''

# 2. src/index.css
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: #f1f5f9;
  overflow: hidden;
}

/* --- BOTTOM SHEET --- */
.bottom-sheet {
  transition: height 0.3s ease-in-out;
  box-shadow: 0 -4px 20px rgba(0,0,0,0.15);
}

/* --- MARCADORES --- */
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
}
.pin-success { background-color: #22c55e; }
.pin-failed { background-color: #ef4444; }
.pin-active { 
  background-color: #eab308; 
  transform: scale(1.2); 
  border: 3px solid white;
  z-index: 1000 !important; 
}
.user-gps-marker {
  background-color: #3b82f6;
  border: 2px solid white;
  border-radius: 50%;
  animation: pulse-blue 2s infinite;
}
@keyframes pulse-blue {
  0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
  70% { box-shadow: 0 0 0 15px rgba(59, 130, 246, 0); }
  100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
}
'''

# 3. src/App.jsx
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useRef } from 'react';
import { Upload, Navigation, Truck, Check, AlertTriangle, ChevronRight, MapPin, Settings, Play, X, Sliders } from 'lucide-react';
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet';
import { Geolocation } from '@capacitor/geolocation';
import 'leaflet/dist/leaflet.css';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import L from 'leaflet';
import 'leaflet-routing-machine';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- ÍCONES ---
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

// --- COMPONENTE MAPA ---
function MapController({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.flyTo(center, zoom, { duration: 1 });
  }, [center, zoom, map]);
  return null;
}

function ActiveRouteLine({ start, end }) {
  const map = useMap();
  const routingControlRef = useRef(null);

  useEffect(() => {
    if (!map || !start || !end) return;
    if (routingControlRef.current) try { map.removeControl(routingControlRef.current); } catch(e) {}

    const plan = L.Routing.plan(
      [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      { createMarker: () => null, addWaypoints: false }
    );

    routingControlRef.current = L.Routing.control({
      waypoints: [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      plan: plan,
      lineOptions: { styles: [{ color: '#3b82f6', weight: 6, opacity: 0.8 }] },
      show: false, addWaypoints: false, fitSelectedRoutes: false
    }).addTo(map);

    return () => {
      if (routingControlRef.current) try { map.removeControl(routingControlRef.current); } catch(e) {}
    };
  }, [map, start, end]);
  return null;
}

export default function App() {
  const [userLocation, setUserLocation] = useState(null);
  const [stops, setStops] = useState([]);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  
  // Modos: 'idle' (sem rota), 'planned' (lista carregada), 'navigating' (em rota)
  const [appMode, setAppMode] = useState('idle'); 
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [showOptModal, setShowOptModal] = useState(false);
  
  const [optConfig, setOptConfig] = useState({ start: 'gps', end: 'any' });

  // 1. INICIALIZAÇÃO E PERMISSÃO
  useEffect(() => {
    checkPermission();
  }, []);

  const checkPermission = async () => {
    try {
      const status = await Geolocation.checkPermissions();
      if (status.location === 'granted') {
        setPermissionGranted(true);
        startTracking();
      } else {
        setPermissionGranted(false);
      }
    } catch (e) {
      // Fallback web
      navigator.permissions.query({ name: 'geolocation' }).then(result => {
         if (result.state === 'granted') {
             setPermissionGranted(true);
             startTracking();
         }
      });
    }
  };

  const requestPermission = async () => {
    try {
      const status = await Geolocation.requestPermissions();
      if (status.location === 'granted') {
        setPermissionGranted(true);
        startTracking();
      } else {
        alert("A localização é necessária para otimizar a rota.");
      }
    } catch (e) {
        alert("Erro ao solicitar permissão. Verifique as configurações do aparelho.");
    }
  };

  const startTracking = () => {
    Geolocation.watchPosition({ enableHighAccuracy: true }, (pos, err) => {
      if (pos) {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
      }
    });
  };

  // 2. IMPORTAÇÃO
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const processData = (dataStr, isBinary) => {
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
        setAppMode('planned');
      } else {
        alert("Erro: Planilha sem colunas Latitude/Longitude.");
      }
    };

    const reader = new FileReader();
    if (file.name.endsWith('.csv')) {
      reader.onload = (evt) => processData(evt.target.result, false);
      reader.readAsText(file);
    } else {
      reader.onload = (evt) => processData(evt.target.result, true);
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

  // 3. OTIMIZAÇÃO (Configurável)
  const runOptimization = () => {
    if (!userLocation && optConfig.start === 'gps') {
      alert("Aguardando GPS...");
      return;
    }

    let points = [...stops];
    let startPoint = null;
    let endPoint = null;
    let optimized = [];

    if (optConfig.start === 'gps') {
      startPoint = userLocation;
    } else {
      const idx = parseInt(optConfig.start);
      startPoint = points[idx];
      optimized.push(points[idx]); 
      points.splice(idx, 1);
    }

    if (optConfig.end !== 'any') {
      const idx = points.findIndex(p => p.id === parseInt(optConfig.end));
      if (idx !== -1) {
        endPoint = points[idx];
        points.splice(idx, 1);
      }
    }

    let current = startPoint;
    while (points.length > 0) {
      let nearestIndex = -1;
      let minDist = Infinity;
      
      for (let i = 0; i < points.length; i++) {
        const d = Math.pow(points[i].lat - current.lat, 2) + Math.pow(points[i].lng - current.lng, 2);
        if (d < minDist) {
          minDist = d;
          nearestIndex = i;
        }
      }
      
      optimized.push(points[nearestIndex]);
      current = points[nearestIndex];
      points.splice(nearestIndex, 1);
    }

    if (endPoint) optimized.push(endPoint);

    setStops(optimized);
    setCurrentStopIndex(0);
    setAppMode('ready'); 
    setShowOptModal(false);
  };

  const startNavigation = () => {
    setAppMode('navigating');
  };

  const handleDelivery = (status) => {
    const newStops = [...stops];
    newStops[currentStopIndex].status = status;
    setStops(newStops);
    
    if (currentStopIndex < stops.length - 1) {
      setCurrentStopIndex(prev => prev + 1);
    } else {
      alert("Rota Finalizada!");
      setAppMode('planned');
    }
  };

  const currentStop = stops[currentStopIndex];

  return (
    <div className="flex flex-col h-screen w-full relative overflow-hidden bg-slate-100">
      
      {!permissionGranted && (
        <div className="absolute inset-0 z-[2000] bg-white flex flex-col items-center justify-center p-6 text-center">
          <MapPin size={64} className="text-blue-500 mb-4 animate-bounce" />
          <h2 className="text-2xl font-bold text-slate-800 mb-2">Permissão de Localização</h2>
          <p className="text-slate-500 mb-6">O MotoristaPro precisa acessar seu GPS para otimizar as rotas.</p>
          <button onClick={requestPermission} className="bg-blue-600 text-white px-8 py-4 rounded-xl font-bold shadow-lg">
            Ativar Localização
          </button>
        </div>
      )}

      <div className="absolute inset-0 z-0 h-full w-full">
        <MapContainer center={[-23.55, -46.63]} zoom={13} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}" attribution="Google" />
          
          {appMode === 'navigating' && currentStop ? (
            <MapController center={[currentStop.lat, currentStop.lng]} zoom={17} />
          ) : (
            userLocation && <MapController center={[userLocation.lat, userLocation.lng]} zoom={14} />
          )}

          {stops.map((stop, idx) => (
             <Marker 
                key={stop.id} 
                position={[stop.lat, stop.lng]} 
                icon={createNumberedIcon(idx + 1, stop.status, (appMode === 'navigating' && idx === currentStopIndex))}
             />
          ))}

          {userLocation && <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon} />}
          
          {appMode === 'navigating' && currentStop && userLocation && (
             <ActiveRouteLine start={userLocation} end={currentStop} />
          )}
        </MapContainer>
      </div>

      <div className={`absolute bottom-0 left-0 right-0 bg-white rounded-t-3xl shadow-[0_-5px_30px_rgba(0,0,0,0.1)] z-[1000] flex flex-col transition-all duration-300
          ${appMode === 'navigating' ? 'h-[25%]' : 'h-[50%]'}`}>
        
        <div className="w-full flex justify-center pt-3 pb-1 cursor-pointer">
           <div className="w-12 h-1.5 bg-gray-300 rounded-full"></div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col px-4 pb-4">
            
            {stops.length === 0 && (
                <div className="flex-1 flex flex-col items-center justify-center text-center">
                    <Truck className="text-blue-200 mb-2" size={48} />
                    <h3 className="font-bold text-lg text-slate-700">Nenhuma rota carregada</h3>
                    <p className="text-xs text-gray-400 mb-4">Importe sua planilha para começar</p>
                    <label className="w-full">
                        <div className="w-full bg-blue-600 text-white py-3 rounded-xl font-bold flex items-center justify-center gap-2 cursor-pointer shadow-lg active:scale-95 transition">
                            <Upload size={18}/> Importar Planilha
                        </div>
                        <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx, .xls" className="hidden" />
                    </label>
                </div>
            )}

            {(appMode === 'planned' || appMode === 'ready') && stops.length > 0 && (
                <div className="flex flex-col h-full">
                    <div className="mb-3">
                         {appMode === 'ready' ? (
                             <button onClick={startNavigation} className="w-full bg-green-600 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2 animate-pulse">
                                <Navigation size={20}/> INICIAR ROTA
                             </button>
                         ) : (
                             <button onClick={() => setShowOptModal(true)} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2">
                                <Sliders size={20}/> OTIMIZAR ROTA
                             </button>
                         )}
                    </div>
                    
                    <div className="flex-1 overflow-y-auto pr-1">
                        <h4 className="text-xs font-bold text-gray-400 uppercase mb-2">Paradas ({stops.length})</h4>
                        {stops.map((stop, idx) => (
                            <div key={idx} className="flex items-center gap-3 py-3 border-b border-gray-100 last:border-0">
                                <div className="font-bold text-gray-400 w-6 text-center">{idx + 1}</div>
                                <div className="flex-1">
                                    <div className="font-bold text-sm text-slate-800">{stop.name}</div>
                                    <div className="text-xs text-gray-500 truncate">{stop.address}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {appMode === 'navigating' && currentStop && (
                <div className="flex flex-col h-full justify-between">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <span className="bg-blue-600 text-white text-[10px] px-2 py-0.5 rounded font-bold">PARADA {currentStopIndex + 1}</span>
                        </div>
                        <h2 className="font-bold text-lg leading-tight">{currentStop.name}</h2>
                        <p className="text-sm text-gray-500 truncate">{currentStop.address}</p>
                    </div>
                    
                    <div className="flex gap-3 mt-2">
                        <button onClick={() => handleDelivery('failed')} className="flex-1 bg-orange-100 text-orange-700 py-3 rounded-xl font-bold text-xs flex flex-col items-center">
                            <AlertTriangle size={16} className="mb-1"/> Ocorrência
                        </button>
                        <button onClick={() => handleDelivery('success')} className="flex-[2] bg-green-600 text-white py-3 rounded-xl font-bold text-sm flex items-center justify-center gap-2 shadow-lg">
                            <Check size={18}/> ENTREGUE
                        </button>
                    </div>
                </div>
            )}
        </div>
      </div>

      {showOptModal && (
          <div className="absolute inset-0 z-[2000] bg-black/50 flex items-center justify-center p-4">
              <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl">
                  <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                      <Settings size={20} className="text-blue-600"/> Configurar Rota
                  </h3>
                  
                  <div className="mb-4">
                      <label className="block text-xs font-bold text-gray-500 mb-1">PONTO DE PARTIDA</label>
                      <select 
                        className="w-full p-3 bg-gray-50 rounded-lg text-sm border focus:border-blue-500 outline-none"
                        value={optConfig.start}
                        onChange={(e) => setOptConfig({...optConfig, start: e.target.value})}
                      >
                          <option value="gps">📍 Minha Localização Atual</option>
                          {stops.map((s, i) => <option key={i} value={i}>{i+1}. {s.name}</option>)}
                      </select>
                  </div>

                  <div className="mb-6">
                      <label className="block text-xs font-bold text-gray-500 mb-1">PONTO DE CHEGADA</label>
                      <select 
                        className="w-full p-3 bg-gray-50 rounded-lg text-sm border focus:border-blue-500 outline-none"
                        value={optConfig.end}
                        onChange={(e) => setOptConfig({...optConfig, end: e.target.value})}
                      >
                          <option value="any">🏁 Otimizar (Mais rápido)</option>
                          {stops.map((s, i) => <option key={s.id} value={s.id}>{i+1}. {s.name}</option>)}
                      </select>
                  </div>

                  <div className="flex gap-3">
                      <button onClick={() => setShowOptModal(false)} className="flex-1 py-3 text-gray-500 font-bold">Cancelar</button>
                      <button onClick={runOptimization} className="flex-[2] bg-blue-600 text-white py-3 rounded-xl font-bold shadow-lg">
                          Confirmar
                      </button>
                  </div>
              </div>
          </div>
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
    print("\n📝 Atualizando V6 Fix...")
    for filename, content in files_content.items():
        # CORREÇÃO AQUI: Só tenta criar pasta se dirname retornar algo
        directory = os.path.dirname(filename)
        if directory:
            os.makedirs(directory, exist_ok=True)
            
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
    print(f"🚀 ATUALIZAÇÃO V6 FIX - {APP_NAME}")
    backup_files()
    update_files()
    
    print("\n📦 Instalando Plugins Nativos...")
    run_command("npm install @capacitor/geolocation", "Install Geo failed")
    run_command("npx cap sync", "Cap Sync failed")

    print("\n☁️ GitHub Push...")
    run_command("git add .", "Add failed")
    run_command('git commit -m "feat: V6 UI e Permissao Fix"', "Commit failed")
    if run_command("git push origin main", "Push failed"):
        print("\n✅ SUCESSO! Código enviado.")
    
    try: os.remove(__file__) 
    except: pass

if __name__ == "__main__":
    main()


