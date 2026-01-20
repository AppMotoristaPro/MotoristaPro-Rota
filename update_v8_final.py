import os
import shutil
import subprocess
from datetime import datetime

# --- CONFIGURAÇÕES ---
REPO_URL = "https://github.com/AppMotoristaPro/MotoristaPro-Rota.git"
BACKUP_ROOT = "backup"
APP_NAME = "MotoristaPro-Rota"

files_content = {}

# 1. ATUALIZAR CSS (Melhorias no Bottom Sheet e Marcadores)
files_content['src/index.css'] = '''@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: 'Inter', sans-serif;
  background-color: #f8fafc;
  overflow: hidden; /* Impede scroll da página inteira */
}

/* --- BOTTOM SHEET --- */
.bottom-sheet {
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 -4px 25px rgba(0,0,0,0.1);
  border-top-left-radius: 24px;
  border-top-right-radius: 24px;
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
.pin-success { background-color: #22c55e; border-color: #f0fdf4; }
.pin-failed { background-color: #ef4444; border-color: #fef2f2; }
.pin-active { 
  background-color: #eab308; 
  transform: scale(1.3); 
  border: 3px solid white;
  z-index: 1000 !important;
  box-shadow: 0 0 15px rgba(234, 179, 8, 0.5);
}

/* GPS DO USUÁRIO (PULSO) */
.user-gps-marker {
  background-color: #2563eb;
  border: 3px solid white;
  border-radius: 50%;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
  animation: pulse 2s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.4); }
  70% { box-shadow: 0 0 0 15px rgba(37, 99, 235, 0); }
  100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0); }
}

/* Ocultar Leaflet Controls padrão que atrapalham no mobile */
.leaflet-routing-container { display: none !important; }
.leaflet-control-zoom { display: none !important; }
'''

# 2. APP.JSX (Lógica V8: Persistência, Navigation Mode, Bottom Sheet Fix)
files_content['src/App.jsx'] = r'''import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Upload, Navigation, Truck, Check, AlertTriangle, ChevronRight, MapPin, Settings, X, Sliders, Trash2, Crosshair } from 'lucide-react';
import { MapContainer, TileLayer, Marker, useMap } from 'react-leaflet';
import { Geolocation } from '@capacitor/geolocation';
import 'leaflet/dist/leaflet.css';
import 'leaflet-routing-machine/dist/leaflet-routing-machine.css';
import L from 'leaflet';
import 'leaflet-routing-machine';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

// --- CONFIGURAÇÃO DE ÍCONES ---
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
  iconSize: [24, 24],
  iconAnchor: [12, 12]
});

// --- COMPONENTES AUXILIARES DE MAPA ---

// Controlador de Câmera Suave
function MapController({ center, zoom, active }) {
  const map = useMap();
  const lastCenter = useRef(null);

  useEffect(() => {
    if (active && center) {
        // Só move se a distância for relevante para evitar "tremedeira"
        if (!lastCenter.current || Math.abs(lastCenter.current.lat - center.lat) > 0.0001 || Math.abs(lastCenter.current.lng - center.lng) > 0.0001) {
            map.flyTo(center, zoom, { animate: true, duration: 1.5 });
            lastCenter.current = center;
        }
    }
  }, [center, zoom, active, map]);
  return null;
}

// Rota Ativa (Linha Azul)
function ActiveRouteLine({ start, end }) {
  const map = useMap();
  const routingControlRef = useRef(null);

  useEffect(() => {
    if (!map || !start || !end) return;

    // Limpa rota anterior
    if (routingControlRef.current) {
        try { map.removeControl(routingControlRef.current); } catch(e) {}
    }

    const plan = L.Routing.plan(
      [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      { createMarker: () => null, addWaypoints: false, draggableWaypoints: false }
    );

    routingControlRef.current = L.Routing.control({
      waypoints: [L.latLng(start.lat, start.lng), L.latLng(end.lat, end.lng)],
      plan: plan,
      lineOptions: { styles: [{ color: '#2563eb', weight: 6, opacity: 0.8 }] },
      show: false, 
      addWaypoints: false, 
      fitSelectedRoutes: false // Importante: Não roubar o zoom do usuário
    }).addTo(map);

    return () => {
      if (routingControlRef.current) {
         try { map.removeControl(routingControlRef.current); } catch(e) {}
      }
    };
  }, [map, start, end]); // Recria apenas se os pontos mudarem
  return null;
}

export default function App() {
  // --- ESTADOS ---
  const [userLocation, setUserLocation] = useState(null);
  const [stops, setStops] = useState([]);
  const [currentStopIndex, setCurrentStopIndex] = useState(0);
  const [appMode, setAppMode] = useState('idle'); // idle, planned, navigating
  const [sheetState, setSheetState] = useState('half'); // min, half, full
  const [showOptModal, setShowOptModal] = useState(false);
  
  // Config Otimização
  const [optConfig, setOptConfig] = useState({ start: 'gps', end: 'any' });

  // 1. PERSISTÊNCIA (Carregar dados salvos ao abrir)
  useEffect(() => {
      const savedStops = localStorage.getItem('motoristaPro_stops');
      const savedMode = localStorage.getItem('motoristaPro_mode');
      const savedIndex = localStorage.getItem('motoristaPro_index');

      if (savedStops) {
          setStops(JSON.parse(savedStops));
          if (savedMode) setAppMode(savedMode);
          if (savedIndex) setCurrentStopIndex(parseInt(savedIndex));
      }
      
      // Iniciar GPS
      checkPermission();
  }, []);

  // 2. SALVAR DADOS (Sempre que mudarem)
  useEffect(() => {
      localStorage.setItem('motoristaPro_stops', JSON.stringify(stops));
      localStorage.setItem('motoristaPro_mode', appMode);
      localStorage.setItem('motoristaPro_index', currentStopIndex.toString());
  }, [stops, appMode, currentStopIndex]);

  // 3. GPS & PERMISSÃO
  const checkPermission = async () => {
    try {
        const status = await Geolocation.checkPermissions();
        if (status.location === 'granted') startTracking();
        else {
            const req = await Geolocation.requestPermissions();
            if (req.location === 'granted') startTracking();
        }
    } catch (e) {
        // Fallback Web
        if (navigator.geolocation) {
             navigator.geolocation.watchPosition(
                (pos) => setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
                (err) => console.log(err),
                { enableHighAccuracy: true }
             );
        }
    }
  };

  const startTracking = () => {
    Geolocation.watchPosition({ enableHighAccuracy: true, timeout: 10000 }, (pos) => {
      if (pos) setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
    });
  };

  // 4. IMPORTAÇÃO
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
        setSheetState('half');
      } else {
        alert("Erro: Não encontramos colunas de endereço/coordenadas.");
      }
    };

    const reader = new FileReader();
    if (file.name.endsWith('.csv')) { reader.onload = (evt) => processData(evt.target.result, false); reader.readAsText(file); } 
    else { reader.onload = (evt) => processData(evt.target.result, true); reader.readAsBinaryString(file); }
  };

  const normalizeData = (rawData) => {
    return rawData.map((row, index) => {
      // Normaliza chaves para lowercase
      const k = Object.keys(row).reduce((acc, key) => { acc[key.toLowerCase().trim()] = row[key]; return acc; }, {});
      
      const lat = parseFloat(k['latitude'] || k['lat'] || 0);
      const lng = parseFloat(k['longitude'] || k['long'] || k['lng'] || 0);
      // Prioridade para a coluna 'stop', depois 'cliente', etc.
      const name = k['stop'] || k['cliente'] || k['nome'] || k['name'] || `Parada ${index + 1}`;
      const address = k['destination address'] || k['endereço'] || k['endereco'] || k['address'] || '---';
      
      return { id: index, name, address, lat, lng };
    }).filter(i => i.lat !== 0 && i.lng !== 0);
  };

  // 5. OTIMIZAÇÃO
  const runOptimization = () => {
    // Se escolheu GPS mas não tem GPS
    if (optConfig.start === 'gps' && !userLocation) {
        alert("Aguardando sinal de GPS... Tente novamente em instantes.");
        return;
    }

    let points = [...stops];
    let startPoint = null;
    let endPoint = null;
    let optimized = [];
    let pendingPoints = points.filter(p => p.status === 'pending');
    let donePoints = points.filter(p => p.status !== 'pending'); // Mantém histórico

    // Define Início
    if (optConfig.start === 'gps') startPoint = userLocation;
    else {
        // Se escolheu um ponto da lista como início
        const startId = parseInt(optConfig.start);
        const pIndex = pendingPoints.findIndex(p => p.id === startId);
        if (pIndex !== -1) {
            startPoint = pendingPoints[pIndex];
            optimized.push(pendingPoints[pIndex]); // Primeiro da rota
            pendingPoints.splice(pIndex, 1);
        }
    }

    // Define Fim (se não for 'any')
    if (optConfig.end !== 'any') {
         const endId = parseInt(optConfig.end);
         const pIndex = pendingPoints.findIndex(p => p.id === endId);
         if (pIndex !== -1) {
             endPoint = pendingPoints[pIndex];
             pendingPoints.splice(pIndex, 1);
         }
    }

    // Algoritmo Vizinho Mais Próximo
    let current = startPoint;
    while (pendingPoints.length > 0) {
      let nearestIndex = -1;
      let minDist = Infinity;
      
      for (let i = 0; i < pendingPoints.length; i++) {
        // Distância Euclidiana (rápida para listas pequenas/médias)
        const d = Math.pow(pendingPoints[i].lat - current.lat, 2) + Math.pow(pendingPoints[i].lng - current.lng, 2);
        if (d < minDist) { minDist = d; nearestIndex = i; }
      }
      
      optimized.push(pendingPoints[nearestIndex]);
      current = pendingPoints[nearestIndex];
      pendingPoints.splice(nearestIndex, 1);
    }

    if (endPoint) optimized.push(endPoint);

    // Reconstrói a lista: Feitos + Novos Otimizados
    setStops([...donePoints, ...optimized]);
    setCurrentStopIndex(donePoints.length); // Aponta para o primeiro pendente
    
    setShowOptModal(false);
    setSheetState('min'); // Minimiza para ver o mapa
    setAppMode('navigating'); // Já inicia navegação
  };

  // 6. AÇÕES DE NAVEGAÇÃO
  const handleDelivery = (status) => {
    const newStops = [...stops];
    newStops[currentStopIndex].status = status;
    setStops(newStops);
    
    // Verifica próximo pendente
    const nextIndex = currentStopIndex + 1;
    if (nextIndex < stops.length) {
      setCurrentStopIndex(nextIndex);
    } else {
      alert("Rota Finalizada!");
      setAppMode('planned');
      setSheetState('half');
    }
  };

  const clearData = () => {
      if (confirm("Tem certeza? Isso apagará toda a rota atual.")) {
          setStops([]);
          setAppMode('idle');
          setSheetState('half');
          setCurrentStopIndex(0);
          localStorage.removeItem('motoristaPro_stops');
      }
  };

  // Toggle do Bottom Sheet
  const toggleSheet = () => {
      if (sheetState === 'min') setSheetState('half');
      else if (sheetState === 'half') setSheetState('full');
      else setSheetState('min');
  };

  const currentStop = stops[currentStopIndex];

  return (
    <div className="flex flex-col h-screen w-full relative overflow-hidden bg-slate-100">
      
      {/* MAPA FUNDO */}
      <div className="absolute inset-0 z-0 h-full w-full">
        <MapContainer center={[-23.55, -46.63]} zoom={13} style={{ height: '100%', width: '100%' }} zoomControl={false}>
          <TileLayer url="https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}" attribution="Google" />
          
          {/* Marcadores */}
          {stops.map((stop, idx) => (
             <Marker 
                key={stop.id} 
                position={[stop.lat, stop.lng]} 
                icon={createNumberedIcon(idx + 1, stop.status, (appMode === 'navigating' && idx === currentStopIndex))}
             />
          ))}

          {/* Marcador Usuário */}
          {userLocation && <Marker position={[userLocation.lat, userLocation.lng]} icon={userIcon} />}
          
          {/* Linha de Rota (Só desenha do Usuário até o Próximo ponto para economizar performance) */}
          {appMode === 'navigating' && currentStop && userLocation && (
             <ActiveRouteLine start={userLocation} end={currentStop} />
          )}

          {/* Controlador de Câmera (Segue o Usuário se estiver navegando, ou foca na parada) */}
          {appMode === 'navigating' && userLocation ? (
              <MapController center={userLocation} zoom={18} active={true} />
          ) : (
             currentStop && <MapController center={[currentStop.lat, currentStop.lng]} zoom={16} active={true} />
          )}

        </MapContainer>
      </div>

      {/* BOTÕES FLUTUANTES TOPO */}
      <div className="absolute top-4 right-4 z-[500] flex flex-col gap-2">
          {appMode !== 'idle' && (
             <button onClick={clearData} className="bg-white p-3 rounded-full shadow-lg text-red-500">
                <Trash2 size={20} />
             </button>
          )}
          {userLocation && (
              <button onClick={() => {}} className="bg-white p-3 rounded-full shadow-lg text-blue-500">
                 <Crosshair size={20} />
              </button>
          )}
      </div>

      {/* BOTTOM SHEET (PAINEL DESLIZANTE) */}
      <div 
         className={`absolute bottom-0 left-0 right-0 bg-white bottom-sheet z-[1000] flex flex-col`}
         style={{ 
             height: sheetState === 'min' ? '180px' : sheetState === 'half' ? '50%' : '92%' 
         }}
      >
        
        {/* Handle (Área de Clique para expandir/reduzir) */}
        <div 
            className="w-full flex justify-center pt-3 pb-3 cursor-pointer bg-white rounded-t-3xl touch-none"
            onClick={toggleSheet}
        >
           <div className="w-12 h-1.5 bg-gray-300 rounded-full"></div>
        </div>

        {/* CONTEÚDO */}
        <div className="flex-1 overflow-hidden flex flex-col px-4 pb-4">
            
            {/* 1. TELA IMPORTAÇÃO */}
            {stops.length === 0 && (
                <div className="flex-1 flex flex-col items-center justify-center text-center">
                    <Truck className="text-blue-200 mb-4" size={54} />
                    <h3 className="font-bold text-xl text-slate-800">Sem rota ativa</h3>
                    <p className="text-sm text-gray-400 mb-6">Importe sua planilha para começar</p>
                    <label className="w-full">
                        <div className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 cursor-pointer shadow-lg active:scale-95 transition">
                            <Upload size={20}/> Importar Planilha
                        </div>
                        <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx, .xls" className="hidden" />
                    </label>
                </div>
            )}

            {/* 2. TELA NAVEGAÇÃO / LISTA */}
            {stops.length > 0 && (
                <div className="flex flex-col h-full">
                    
                    {/* CABEÇALHO DA PARADA ATUAL */}
                    {appMode === 'navigating' && currentStop ? (
                        <div className="mb-4 bg-blue-50 p-4 rounded-xl border border-blue-100">
                             <div className="flex justify-between items-start mb-1">
                                <span className="bg-blue-600 text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase tracking-wider">
                                    Parada {currentStopIndex + 1}
                                </span>
                                <span className="text-xs text-blue-400 font-bold">{currentStopIndex + 1}/{stops.length}</span>
                             </div>
                             <h2 className="font-bold text-xl text-slate-800 leading-tight mb-1">{currentStop.name}</h2>
                             <p className="text-sm text-slate-500 truncate">{currentStop.address}</p>
                             
                             <div className="flex gap-3 mt-4">
                                <button onClick={() => handleDelivery('failed')} className="flex-1 bg-white border border-orange-200 text-orange-600 py-3 rounded-lg font-bold text-xs flex items-center justify-center gap-1 shadow-sm">
                                    <AlertTriangle size={14}/> Ocorrência
                                </button>
                                <button onClick={() => handleDelivery('success')} className="flex-[2] bg-green-600 text-white py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 shadow-md active:scale-95 transition">
                                    <Check size={18}/> ENTREGUE
                                </button>
                             </div>
                        </div>
                    ) : (
                        // BOTÃO OTIMIZAR (SE NÃO ESTIVER NAVEGANDO)
                        <div className="mb-4">
                             <button onClick={() => setShowOptModal(true)} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold shadow-lg flex items-center justify-center gap-2">
                                <Sliders size={20}/> CONFIGURAR & OTIMIZAR
                             </button>
                        </div>
                    )}
                    
                    {/* LISTA DE PARADAS (SCROLL) */}
                    <div className="flex-1 overflow-y-auto pr-1 pb-safe">
                        <h4 className="text-[10px] font-bold text-gray-400 uppercase tracking-widest mb-3 sticky top-0 bg-white py-2">Próximas Paradas</h4>
                        {stops.map((stop, idx) => {
                            if (stop.status !== 'pending' && idx !== currentStopIndex) return null; // Esconde as já feitas para limpar
                            const isCurrent = idx === currentStopIndex;
                            return (
                                <div key={idx} className={`flex items-center gap-4 py-3 border-b border-gray-100 last:border-0 ${isCurrent ? 'opacity-100' : 'opacity-60'}`}>
                                    <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${isCurrent ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-500'}`}>
                                        {idx + 1}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="font-bold text-sm text-slate-800 truncate">{stop.name}</div>
                                        <div className="text-xs text-gray-400 truncate">{stop.address}</div>
                                    </div>
                                    {isCurrent && <ChevronRight size={16} className="text-blue-500" />}
                                </div>
                            )
                        })}
                         {/* Histórico botão */}
                        {stops.filter(s => s.status !== 'pending').length > 0 && (
                            <div className="text-center py-4 text-xs text-gray-400">
                                {stops.filter(s => s.status !== 'pending').length} entregas finalizadas
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
      </div>

      {/* MODAL OTIMIZAÇÃO */}
      {showOptModal && (
          <div className="absolute inset-0 z-[2000] bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4">
              <div className="bg-white w-full sm:max-w-sm rounded-t-2xl sm:rounded-2xl p-6 shadow-2xl animate-in slide-in-from-bottom-10">
                  <div className="flex justify-between items-center mb-6">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                        <Settings size={20} className="text-blue-600"/> Otimizar Rota
                    </h3>
                    <button onClick={() => setShowOptModal(false)} className="text-gray-400"><X size={24}/></button>
                  </div>
                  
                  <div className="space-y-4 mb-6">
                      <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">PONTO DE PARTIDA</label>
                          <select 
                            className="w-full p-4 bg-slate-50 rounded-xl text-sm font-medium border-0 focus:ring-2 focus:ring-blue-500 outline-none"
                            value={optConfig.start}
                            onChange={(e) => setOptConfig({...optConfig, start: e.target.value})}
                          >
                              <option value="gps">📍 Minha Localização (GPS)</option>
                              {stops.map((s, i) => <option key={i} value={i}>{i+1}. {s.name}</option>)}
                          </select>
                      </div>

                      <div>
                          <label className="block text-[10px] font-bold text-gray-400 uppercase mb-1">PONTO DE CHEGADA</label>
                          <select 
                            className="w-full p-4 bg-slate-50 rounded-xl text-sm font-medium border-0 focus:ring-2 focus:ring-blue-500 outline-none"
                            value={optConfig.end}
                            onChange={(e) => setOptConfig({...optConfig, end: e.target.value})}
                          >
                              <option value="any">🏁 Otimizar (Mais Rápido)</option>
                              {stops.map((s, i) => <option key={s.id} value={s.id}>{i+1}. {s.name}</option>)}
                          </select>
                      </div>
                  </div>

                  <button onClick={runOptimization} className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold text-lg shadow-lg shadow-blue-200 active:scale-95 transition">
                      Confirmar Rota
                  </button>
              </div>
          </div>
      )}

    </div>
  );
}'''

# --- FUNÇÕES ---
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
    print("\n📝 Atualizando V8 Final...")
    for filename, content in files_content.items():
        directory = os.path.dirname(filename)
        if directory: os.makedirs(directory, exist_ok=True)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ {filename}")

def run_command(command, msg):
    try: subprocess.run(command, shell=True, check=True); return True
    except: print(f"❌ {msg}"); return False

def main():
    print(f"🚀 ATUALIZAÇÃO V8 (UX FINAL) - {APP_NAME}")
    backup_files()
    update_files()
    print("\n☁️ GitHub Push...")
    run_command("git add .", "Add failed")
    run_command('git commit -m "feat: V8 Persistence, Better Nav & Bottom Sheet Fix"', "Commit failed")
    if run_command("git push origin main", "Push failed"):
        print("\n✅ SUCESSO! Código enviado.")
    
    try:
        os.remove(__file__)
    except:
        pass

if __name__ == "__main__":
    main()


