import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. CSS (Estilo do Painel de Debug)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;
@import 'maplibre-gl/dist/maplibre-gl.css';

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: #F8FAFC;
  color: #0F172A;
  overflow: hidden; /* Importante para o mapa não scrollar a página */
}

.map-container { width: 100%; height: 100%; }

/* DEBUG PANEL STYLE */
.debug-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 200px;
  background: rgba(0, 0, 0, 0.85);
  color: #00ff00;
  font-family: monospace;
  font-size: 10px;
  z-index: 9999;
  padding: 10px;
  overflow-y: auto;
  pointer-events: all; /* Permite rolar o log */
  display: flex;
  flex-direction: column;
}

.debug-row { border-bottom: 1px solid #333; padding: 2px 0; }
.debug-error { color: #ff4444; font-weight: bold; }
.debug-btn { 
  margin-top: 5px; 
  background: #2563EB; 
  color: white; 
  padding: 8px; 
  border-radius: 4px; 
  text-align: center; 
  font-weight: bold; 
  font-size: 12px;
}

/* Cards & UI */
.modern-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
  border: 1px solid #f1f5f9;
}
.fab-main { background: #0F172A; color: white; }
.btn-action-lg { height: 50px; display: flex; flex-direction: column; align-items: center; justify-content: center; }
'''

# 2. APP.JSX (Instrumentado com Logs)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Upload, Navigation, Check, AlertTriangle, Trash2, Plus, ArrowLeft, Sliders, MapPin, Package, Clock, ChevronDown, ChevronUp, Box, Map as MapIcon, Loader2, Search, X, List, Crosshair, Copy } from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Map, { Marker, NavigationControl } from 'react-map-gl/maplibre';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

const DB_KEY = 'mp_db_v30_debug';

// --- DEBUG LOGGER ---
const useLogger = () => {
    const [logs, setLogs] = useState([]);
    const addLog = (msg, type='info') => {
        const time = new Date().toISOString().split('T')[1].slice(0,8);
        setLogs(prev => [`[${time}] ${msg}`, ...prev].slice(0, 50)); // Mantém últimos 50
    };
    return { logs, addLog };
};

// --- HELPERS ---
const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    stops.forEach(stop => {
        const rawName = stop.name ? String(stop.name) : 'Sem Nome';
        const key = rawName.trim().toLowerCase();
        if (!groups[key]) {
            groups[key] = { id: key, lat: stop.lat, lng: stop.lng, mainName: rawName, mainAddress: stop.address, items: [], status: 'pending' };
        }
        groups[key].items.push(stop);
    });
    return Object.values(groups); // Simplificado para debug
};

export default function App() {
  const { logs, addLog } = useLogger();
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  const [userPos, setUserPos] = useState(null);
  const [showMap, setShowMap] = useState(false);
  
  // Ref para capturar erros do mapa
  const mapRef = useRef(null);

  // INIT
  useEffect(() => {
    addLog("App Iniciado v30");
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            setRoutes(parsed);
            addLog(`Rotas carregadas: ${parsed.length}`);
        } else {
            addLog("Nenhuma rota salva encontrada.");
        }
    } catch (e) { addLog(`Erro ao carregar Storage: ${e.message}`, 'error'); }
    
    startGps();
  }, []);

  const startGps = async () => {
      addLog("Iniciando GPS...");
      try {
          const perm = await Geolocation.checkPermissions();
          addLog(`Permissão GPS: ${perm.location}`);
          
          if(perm.location !== 'granted') {
              await Geolocation.requestPermissions();
          }

          Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 5000 }, (pos) => {
              if(pos) {
                  setUserPos({ lat: pos.coords.latitude, lng: pos.coords.longitude });
                  // Loga apenas a cada 10 updates para não spammar, ou se for o primeiro
                  if(Math.random() > 0.9) addLog(`GPS Update: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
              }
          });
      } catch (e) {
          addLog(`ERRO CRÍTICO GPS: ${e.message}`, 'error');
      }
  };

  const copyDebug = () => {
      const text = logs.join('\n');
      navigator.clipboard.writeText(text).then(() => alert("Log copiado! Cole no chat.")).catch(e => alert("Erro ao copiar."));
  };

  const handleFileUpload = (e) => {
    addLog("Iniciando Upload...");
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (evt) => {
        try {
            const bstr = evt.target.result;
            const wb = XLSX.read(bstr, {type:'binary'});
            const data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
            addLog(`Linhas brutas lidas: ${data.length}`);
            
            const norm = data.map((r, i) => ({
                id: Date.now() + i,
                name: String(r['Stop'] || r['Cliente'] || 'Sem Nome'),
                address: String(r['Address'] || r['Endereço'] || '---'),
                lat: parseFloat(r['Latitude'] || r['Lat'] || 0),
                lng: parseFloat(r['Longitude'] || r['Lng'] || 0),
                status: 'pending'
            })).filter(i => i.lat !== 0);

            if(norm.length > 0) {
                const newRoute = { id: Date.now(), name: "Rota Debug " + Date.now(), date: new Date().toLocaleDateString(), stops: norm, optimized: false };
                setRoutes([newRoute, ...routes]);
                setView('home');
                addLog(`Rota criada com ${norm.length} paradas válidas.`);
            } else {
                addLog("FALHA: Nenhuma coordenada válida encontrada.", 'error');
                alert("Erro: Planilha sem colunas Latitude/Longitude.");
            }
        } catch(err) {
            addLog(`ERRO PARSE: ${err.message}`, 'error');
        }
    };
    reader.readAsBinaryString(file);
  };

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute]);
  
  // Render
  return (
    <div className="flex flex-col h-screen bg-slate-50 relative">
        {/* DEBUG OVERLAY */}
        <div className="debug-overlay">
            <div style={{display:'flex', justifyContent:'space-between'}}>
                <strong>DEBUG CONSOLE v30</strong>
                <button onClick={() => setView('home')} style={{color:'white'}}>Home</button>
            </div>
            <div className="flex-1 overflow-y-auto">
                {logs.map((l, i) => <div key={i} className={`debug-row ${l.includes('ERRO') ? 'debug-error' : ''}`}>{l}</div>)}
            </div>
            <div className="debug-btn" onClick={copyDebug}>COPIAR LOG PARA SUPORTE</div>
        </div>

        <div style={{marginTop: '200px', height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column'}}>
            
            {view === 'home' && (
                <div className="p-6">
                    <h1 className="text-2xl font-bold mb-4">Minhas Rotas</h1>
                    {routes.map(r => (
                        <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); addLog(`Abrindo rota: ${r.id}`); }} className="modern-card p-4 mb-4">
                            <b>{r.name}</b> ({r.stops.length} stops)
                        </div>
                    ))}
                    <label className="block w-full p-4 bg-blue-100 text-blue-700 text-center rounded-xl font-bold mt-4">
                        + IMPORTAR PLANILHA AGORA
                        <input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/>
                    </label>
                </div>
            )}

            {view === 'details' && (
                <div className="flex flex-col h-full">
                    <div className="bg-white p-4 shadow flex gap-2">
                        <button onClick={() => setShowMap(!showMap)} className="flex-1 bg-slate-200 p-2 rounded">
                            {showMap ? 'Ver Lista' : 'Ver Mapa'}
                        </button>
                    </div>

                    {showMap ? (
                        <div className="flex-1 relative bg-gray-200">
                            <Map 
                                initialViewState={{
                                    longitude: userPos?.lng || -46.63,
                                    latitude: userPos?.lat || -23.55,
                                    zoom: 12
                                }}
                                style={{width: '100%', height: '100%'}}
                                mapStyle="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json"
                                onLoad={() => addLog("Mapa Carregado (onLoad)")}
                                onError={(e) => addLog(`ERRO MAPA: ${e.error.message}`, 'error')}
                            >
                                <NavigationControl />
                                {groupedStops.map((g, i) => (
                                    <Marker key={i} longitude={g.lng} latitude={g.lat} color="blue" />
                                ))}
                                {userPos && <Marker longitude={userPos.lng} latitude={userPos.lat} color="red" />}
                            </Map>
                        </div>
                    ) : (
                        <div className="flex-1 overflow-y-auto p-4">
                            {groupedStops.map((g, i) => (
                                <div key={i} className="modern-card p-4 mb-2">
                                    {g.mainName} <br/><small>{g.lat}, {g.lng}</small>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    </div>
  );
}
'''

def main():
    print(f"🚀 ATUALIZAÇÃO V30 (DEBUGGER) - {APP_NAME}")
    
    print("\n📝 Atualizando arquivos...")
    for f, c in files_content.items():
        dir_name = os.path.dirname(f)
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        with open(f, 'w', encoding='utf-8') as file: file.write(c)
        print(f"   ✅ {f}")
        
    print("\n☁️ Enviando para GitHub...")
    subprocess.run("git add .", shell=True)
    subprocess.run('git commit -m "chore: V30 Debug Mode"', shell=True)
    subprocess.run("git push origin main", shell=True)
    
    try: os.remove(__file__)
    except: pass

if __name__ == "__main__":
    main()



