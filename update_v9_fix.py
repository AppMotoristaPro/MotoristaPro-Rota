import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. REMOVER O PLUGIN PESADO (Routing Machine) DO PACKAGE.JSON
files_content['package.json'] = '''{
  "name": "motorista-pro-rota",
  "private": true,
  "version": "1.4.0",
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

# 2. CSS PARA CLONAR O GOOGLE MAPS
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Roboto', 'Inter', sans-serif;
  background-color: #fff;
  overflow: hidden;
}

/* Esconder créditos do mapa para visual limpo (Google Style) */
.leaflet-control-attribution { display: none !important; }
.leaflet-control-zoom { display: none !important; }

/* Marcadores */
.custom-pin {
  background-color: #EA4335; /* Vermelho Google */
  border: 2px solid white;
  border-radius: 50%;
  color: white;
  font-weight: bold;
  font-size: 13px;
  display: flex !important;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 5px rgba(0,0,0,0.4);
}
.pin-success { background-color: #34A853; } /* Verde Google */
.pin-failed { background-color: #FBBC05; border-color: #fff; color: #333; } /* Amarelo Google */
.pin-active { 
  background-color: #4285F4; /* Azul Google */
  transform: scale(1.3); 
  border: 3px solid white;
  z-index: 9999 !important;
}

/* GPS DO USUÁRIO */
.user-gps-dot {
  background-color: #4285F4;
  border: 2px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 10px rgba(66, 133, 244, 0.2);
}

/* BOTTOM SHEET GOOGLE STYLE */
.google-sheet {
  box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
  transition: height 0.3s cubic-bezier(0.25, 1, 0.5, 1);
}

/* BARRA DE BUSCA FLUTUANTE */
.google-search-bar {
  box-shadow: 0 2px 6px rgba(0,0,0,0.2);
}
'''

# 3. APP.JSX (LÓGICA OTIMIZADA + VISUAL GOOGLE)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useRef } from 'react';
import { Upload, Navigation, Check, AlertTriangle, ChevronRight, MapPin, Settings, X, Sliders, Menu, Search, User, Trash2, Locate } from 'lucide-react';
import { MapContainer, TileLayer, Marker, useMap, Polyline } from 'react-leaflet';
import { Geolocation } from '@capacitor/geolocation';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// Ícones Customizados
const createIcon = (number, status, isActive) => {
  let className = 'custom-pin';
  if (status === 'success') className += ' pin-success';
  else if (status === 'failed') className += ' pin-failed';
  else if (isActive) className += ' pin-active';

  return L.divIcon({
    className: className,
    html: `<span>${status === 'success' ? '✓' : number}</span>`,
    iconSize: isActive ? [40, 40] : [28, 28],
    iconAnchor: isActive ? [20, 40] : [14, 28] // Pino ancora na ponta inferior
  });
};

const userIcon = L.divIcon({ className: 'user-gps-dot', iconSize: [16, 16], iconAnchor: [8, 8] });

// --- COMPONENTES LEAFLET ---
function MapController({ center, zoom, active }) {
  const map = useMap();
  useEffect(() => {
    if (active && center) map.flyTo(center, zoom, { animate: true, duration: 1.2 });
  }, [center, zoom, active, map]);
  return null;
}

// Rota Leve (Polyline Simples)
function SimpleRoute({ start, end }) {
    // Linha reta estilizada para evitar lag de cálculo
    return <Polyline positions={[[start.lat, start.lng], [end.lat, end.lng]]} pathOptions={{ color: '#4285F4', weight: 4, opacity: 0.7, dashArray: '10, 10' }} />
}

export default function App() {
  const [userLocation, setUserLocation] = useState(null);
  const [stops, setStops] = useState([]);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  const [appMode, setAppMode] = useState('idle'); 
  const [showOptModal, setShowOptModal] = useState(false);
  const [optConfig, setOptConfig] = useState({ start: 'gps', end: 'any' });
  const [sheetOpen, setSheetOpen] = useState(true);

  // Persistência
  useEffect(() => {
      const saved = localStorage.getItem('mp_stops');
      if (saved) {
          setStops(JSON.parse(saved));
          setAppMode('planned');
      }
      checkPermission();
  }, []);

  useEffect(() => {
      localStorage.setItem('mp_stops', JSON.stringify(stops));
  }, [stops]);

  const checkPermission = async () => {
    try { await Geolocation.requestPermissions(); startTracking(); } catch(e) { startTracking(); }
  };

  const startTracking = () => {
    Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
      if (pos) setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
    });
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    const process = (d, bin) => {
        let data = [];
        if(bin) {
            const wb = XLSX.read(d, {type:'binary'});
            data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
        } else {
            data = Papa.parse(d, {header:true, skipEmptyLines:true}).data;
        }
        const norm = data.map((r, i) => {
             const k = Object.keys(r).reduce((acc, key) => { acc[key.toLowerCase().trim()] = r[key]; return acc; }, {});
             return {
                 id: i,
                 name: k['stop'] || k['cliente'] || k['nome'] || `Cliente ${i+1}`,
                 address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                 lat: parseFloat(k['latitude'] || k['lat'] || 0),
                 lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                 status: 'pending'
             };
        }).filter(i => i.lat !== 0);
        
        if(norm.length) { setStops(norm); setAppMode('planned'); setSheetOpen(true); }
        else alert("Erro: Planilha inválida");
    };
    if(file.name.endsWith('.csv')) { reader.onload = (e) => process(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = (e) => process(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const runOptimization = () => {
      if (!userLocation && optConfig.start === 'gps') { alert("Aguardando GPS..."); return; }
      let points = [...stops];
      let start = optConfig.start === 'gps' ? userLocation : points[parseInt(optConfig.start)];
      let optimized = [];
      let pending = points.filter(p => p.status === 'pending');
      let done = points.filter(p => p.status !== 'pending');

      // Remove start from pending if it's in list
      if (optConfig.start !== 'gps') pending = pending.filter(p => p.id !== parseInt(optConfig.start));
      if (optConfig.start !== 'gps') optimized.push(points.find(p => p.id === parseInt(optConfig.start)));

      let current = start;
      while(pending.length > 0) {
          let nearIdx = -1, min = Infinity;
          for(let i=0; i<pending.length; i++) {
              const d = (pending[i].lat - current.lat)**2 + (pending[i].lng - current.lng)**2;
              if(d < min) { min = d; nearIdx = i; }
          }
          optimized.push(pending[nearIdx]);
          current = pending[nearIdx];
          pending.splice(nearIdx, 1);
      }
      setStops([...done, ...optimized]);
      setCurrentStopIndex(done.length);
      setAppMode('navigating');
      setSheetOpen(false); // Minimiza para ver mapa
      setShowOptModal(false);
  };

  const handleDelivery = (status) => {
      const newStops = [...stops];
      newStops[currentStopIndex].status = status;
      setStops(newStops);
      if(currentStopIndex < stops.length -1) setCurrentStopIndex(p => p+1);
      else { alert("Rota Finalizada!"); setAppMode('planned'); setSheetOpen(true); }
  };

  const openGoogleMaps = () => {
      const stop = stops[currentStopIndex];
      // URL Universal que o Android intercepta e abre o App Nativo
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}&travelmode=driving`, '_system');
  };

  const clearRoute = () => {
      if(confirm("Apagar rota atual?")) { setStops([]); setAppMode('idle'); localStorage.removeItem('mp_stops'); }
  };

  const currentStop = stops[currentStopIndex];

  return (
    <div className="flex flex-col h-screen w-full relative bg-white">
      
      {/* 1. BARRA DE BUSCA FLUTUANTE (Estilo Google Maps) */}
      <div className="absolute top-4 left-4 right-4 z-[800] flex gap-3">
          <div className="flex-1 bg-white rounded-full h-12 flex items-center px-4 shadow-md border border-gray-100 google-search-bar">
              <Menu className="text-gray-500 mr-3" size={24} onClick={() => setSheetOpen(!sheetOpen)}/>
              <div className="flex-1 text-gray-700 font-medium truncate">
                  {appMode === 'navigating' ? `Navegando: ${currentStop?.name}` : 'MotoristaPro Rota'}
              </div>
              {stops.length > 0 ? (
                  <Trash2 className="text-red-500 ml-2" size={20} onClick={clearRoute}/>
              ) : (
                  <User className="text-blue-500 ml-2" size={24}/>
              )}
          </div>
      </div>

      {/* 2. MAPA FUNDO (Google Hybrid Look) */}
      <div className="absolute inset-0 z-0">
        <MapContainer center={[-23.55, -46.63]} zoom={15} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          {/* Tile Layer Google Traffic/Hybrid */}
          <TileLayer url="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}" />
          
          {stops.map((stop, idx) => {
               // Renderiza apenas os pendentes ou o último feito para performance
               if(stop.status !== 'pending' && idx !== currentStopIndex) return null;
               return <Marker key={idx} position={[stop.lat, stop.lng]} icon={createIcon(idx+1, stop.status, idx === currentStopIndex)} />
          })}
          
          {userLocation && <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon} />}
          
          {/* Linha Simples (Zero Lag) */}
          {appMode === 'navigating' && currentStop && userLocation && <SimpleRoute start={userLocation} end={currentStop} />}
          
          {/* Auto Focus */}
          {appMode === 'navigating' && userLocation && <MapController center={userLocation} zoom={18} active={!sheetOpen} />}
        </MapContainer>
      </div>

      {/* 3. BOTÃO GPS RECENTER */}
      {userLocation && (
        <div className="absolute bottom-48 right-4 z-[800]">
            <button className="bg-white p-3 rounded-full shadow-lg text-blue-600" onClick={() => setSheetOpen(false)}>
                <Locate size={24} />
            </button>
        </div>
      )}

      {/* 4. BOTTOM SHEET GOOGLE STYLE */}
      <div className={`absolute bottom-0 left-0 right-0 bg-white z-[900] google-sheet flex flex-col ${sheetOpen ? 'h-[55%]' : 'h-[25%]'}`}>
          <div className="w-full flex justify-center py-2 cursor-pointer" onClick={() => setSheetOpen(!sheetOpen)}>
              <div className="w-10 h-1 bg-gray-300 rounded-full"></div>
          </div>

          <div className="flex-1 px-5 pb-5 overflow-hidden flex flex-col">
              
              {/* VAZIO */}
              {stops.length === 0 && (
                  <div className="flex-1 flex flex-col items-center justify-center">
                      <h3 className="text-xl font-bold text-gray-800 mb-2">Explore a área</h3>
                      <p className="text-gray-500 mb-6 text-center">Importe sua rota para começar a navegar.</p>
                      <label className="bg-blue-600 text-white px-6 py-3 rounded-full font-bold shadow-lg flex items-center gap-2 cursor-pointer">
                          <Upload size={20}/> Importar Rota
                          <input type="file" onChange={handleFileUpload} accept=".csv,.xlsx" className="hidden"/>
                      </label>
                  </div>
              )}

              {/* LISTA DE PARADAS */}
              {stops.length > 0 && appMode !== 'navigating' && (
                  <div className="flex flex-col h-full">
                      <div className="flex justify-between items-center mb-4">
                          <h2 className="font-bold text-lg">{stops.length} Locais</h2>
                          <button onClick={() => setShowOptModal(true)} className="bg-blue-100 text-blue-700 px-4 py-2 rounded-full text-sm font-bold flex gap-2">
                              <Sliders size={16}/> Otimizar
                          </button>
                      </div>
                      <div className="flex-1 overflow-y-auto">
                          {stops.map((stop, i) => (
                              <div key={i} className="flex gap-4 mb-4 items-start">
                                  <div className="text-gray-500 font-bold text-sm mt-1">{i+1}</div>
                                  <div className="flex-1 border-b border-gray-100 pb-3">
                                      <div className="font-bold text-gray-800">{stop.name}</div>
                                      <div className="text-sm text-gray-500">{stop.address}</div>
                                  </div>
                              </div>
                          ))}
                      </div>
                  </div>
              )}

              {/* MODO NAVEGAÇÃO (ESTILO GOOGLE MAPS GO) */}
              {appMode === 'navigating' && currentStop && (
                  <div className="flex flex-col h-full justify-between">
                      <div>
                          <div className="flex items-center justify-between mb-1">
                              <h2 className="text-2xl font-bold text-gray-900 truncate">{currentStop.name}</h2>
                              <span className="bg-gray-100 text-gray-600 px-2 py-1 rounded text-xs font-bold">{currentStopIndex+1}/{stops.length}</span>
                          </div>
                          <p className="text-gray-500 mb-4 truncate">{currentStop.address}</p>
                          
                          {/* BOTÃO PRINCIPAL DE NAVEGAÇÃO */}
                          <button onClick={openGoogleMaps} className="w-full bg-blue-600 text-white py-3 rounded-full font-bold text-lg shadow-lg flex items-center justify-center gap-2 mb-4">
                              <Navigation size={22}/> Iniciar Navegação
                          </button>
                      </div>

                      <div className="grid grid-cols-2 gap-3">
                          <button onClick={() => handleDelivery('failed')} className="bg-white border border-gray-200 text-gray-700 py-3 rounded-full font-bold text-sm">
                              Não Entregue
                          </button>
                          <button onClick={() => handleDelivery('success')} className="bg-green-600 text-white py-3 rounded-full font-bold text-sm shadow-md">
                              Concluir Entrega
                          </button>
                      </div>
                  </div>
              )}
          </div>
      </div>

      {/* MODAL OPT */}
      {showOptModal && (
          <div className="absolute inset-0 z-[2000] bg-black/50 flex items-center justify-center p-4">
              <div className="bg-white w-full max-w-sm rounded-2xl p-6 shadow-2xl">
                  <h3 className="text-lg font-bold mb-4">Configurar Rota</h3>
                  <div className="space-y-4 mb-6">
                      <div>
                          <label className="text-xs font-bold text-gray-400">PARTIDA</label>
                          <select className="w-full p-3 bg-gray-50 rounded-lg mt-1" onChange={e => setOptConfig({...optConfig, start: e.target.value})}>
                              <option value="gps">Meu GPS</option>
                              {stops.map((s,i) => <option key={i} value={i}>{s.name}</option>)}
                          </select>
                      </div>
                      <div>
                          <label className="text-xs font-bold text-gray-400">DESTINO</label>
                          <select className="w-full p-3 bg-gray-50 rounded-lg mt-1" onChange={e => setOptConfig({...optConfig, end: e.target.value})}>
                              <option value="any">Automático</option>
                              {stops.map((s,i) => <option key={i} value={s.id}>{s.name}</option>)}
                          </select>
                      </div>
                  </div>
                  <div className="flex gap-3">
                      <button onClick={() => setShowOptModal(false)} className="flex-1 text-gray-500 font-bold">Cancelar</button>
                      <button onClick={runOptimization} className="flex-1 bg-blue-600 text-white py-3 rounded-xl font-bold">Confirmar</button>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
}'''

def main():
    print(f"🚀 ATUALIZAÇÃO V9 FIX (Google Style) - {APP_NAME}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_base = f"{BACKUP_ROOT}/{ts}"
    os.makedirs(backup_base, exist_ok=True)
    
    print("\n📝 Escrevendo arquivos...")
    for f, c in files_content.items():
        # Lógica de Backup Corrigida
        if os.path.exists(f): 
            dest = f"{backup_base}/{f}"
            dest_dir = os.path.dirname(dest)
            if dest_dir: os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(f, dest)
        
        # Lógica de Escrita
        dir_name = os.path.dirname(f)
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "feat: V9 Google Maps Clone UI + No Lag Fix"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    # Autodestruição
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()


