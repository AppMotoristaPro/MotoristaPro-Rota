import React, { useState, useEffect } from 'react';
import { Upload, Navigation, Check, AlertTriangle, Trash2, Plus, MapPin, ChevronRight, Package, ArrowLeft, Sliders, Play } from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';

export default function App() {
  // --- ESTADOS ---
  const [routes, setRoutes] = useState([]); // Lista de rotas salvas
  const [activeRouteId, setActiveRouteId] = useState(null); // ID da rota sendo visualizada
  const [view, setView] = useState('home'); // 'home', 'create', 'details'
  
  // Estado para criação
  const [newRouteName, setNewRouteName] = useState('');
  const [tempStops, setTempStops] = useState([]);

  // --- PERSISTÊNCIA ---
  useEffect(() => {
    const saved = localStorage.getItem('mp_routes_v10');
    if (saved) setRoutes(JSON.parse(saved));
  }, []);

  useEffect(() => {
    localStorage.setItem('mp_routes_v10', JSON.stringify(routes));
  }, [routes]);

  // --- GEOLOCALIZAÇÃO ---
  const getCurrentLocation = async () => {
    try {
      const pos = await Geolocation.getCurrentPosition();
      return { lat: pos.coords.latitude, lng: pos.coords.longitude };
    } catch (e) {
      alert("Erro ao pegar GPS. Verifique se a localização está ativa.");
      return null;
    }
  };

  // --- IMPORTAÇÃO ---
  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

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
                 id: Date.now() + i, // ID único
                 name: k['stop'] || k['cliente'] || k['nome'] || `Cliente ${i+1}`,
                 address: k['destination address'] || k['endereço'] || k['endereco'] || '---',
                 lat: parseFloat(k['latitude'] || k['lat'] || 0),
                 lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                 status: 'pending' // pending, success, failed
             };
        }).filter(i => i.lat !== 0);

        if(norm.length) setTempStops(norm);
        else alert("Erro: Planilha inválida ou sem coordenadas.");
    };

    const reader = new FileReader();
    if(file.name.endsWith('.csv')) { reader.onload = (e) => process(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = (e) => process(e.target.result, true); reader.readAsBinaryString(file); }
  };

  // --- CRUD ROTAS ---
  const saveNewRoute = () => {
      if(!newRouteName.trim()) return alert("Dê um nome para a rota!");
      if(tempStops.length === 0) return alert("Importe uma planilha primeiro!");

      const newRoute = {
          id: Date.now(),
          name: newRouteName,
          date: new Date().toLocaleDateString(),
          stops: tempStops
      };

      setRoutes([newRoute, ...routes]);
      setNewRouteName('');
      setTempStops([]);
      setView('home');
  };

  const deleteRoute = (id) => {
      if(confirm("Excluir esta rota permanentemente?")) {
          setRoutes(routes.filter(r => r.id !== id));
          if(activeRouteId === id) setView('home');
      }
  };

  // --- OTIMIZAÇÃO ---
  const optimizeActiveRoute = async () => {
      const userLoc = await getCurrentLocation();
      if(!userLoc) return; // Se falhar GPS, aborta

      // Encontra a rota ativa
      const routeIdx = routes.findIndex(r => r.id === activeRouteId);
      if(routeIdx === -1) return;

      const currentStops = [...routes[routeIdx].stops];
      let pending = currentStops.filter(s => s.status === 'pending');
      let done = currentStops.filter(s => s.status !== 'pending');
      
      let optimized = [];
      let currentPos = userLoc;

      while(pending.length > 0) {
          let nearIdx = -1, min = Infinity;
          for(let i=0; i<pending.length; i++) {
              const d = (pending[i].lat - currentPos.lat)**2 + (pending[i].lng - currentPos.lng)**2;
              if(d < min) { min = d; nearIdx = i; }
          }
          optimized.push(pending[nearIdx]);
          currentPos = pending[nearIdx]; // O próximo ponto vira a referência
          pending.splice(nearIdx, 1);
      }

      // Atualiza a rota
      const updatedRoutes = [...routes];
      updatedRoutes[routeIdx].stops = [...done, ...optimized];
      setRoutes(updatedRoutes);
      alert("Rota otimizada com base na sua localização atual!");
  };

  // --- NAVEGAÇÃO EXTERNA ---
  const openNavigation = (stop) => {
      // Tenta abrir direto no Waze ou Maps
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${stop.lat},${stop.lng}&travelmode=driving`, '_system');
  };

  // --- AÇÕES DE ENTREGA ---
  const handleStatus = (stopId, status) => {
      const routeIdx = routes.findIndex(r => r.id === activeRouteId);
      if(routeIdx === -1) return;

      const updatedRoutes = [...routes];
      const stops = updatedRoutes[routeIdx].stops;
      const stopIndex = stops.findIndex(s => s.id === stopId);
      
      if(stopIndex !== -1) {
          stops[stopIndex].status = status;
          setRoutes(updatedRoutes);

          // Lógica de Auto-Avanço
          // Procura o próximo pendente
          const nextStop = stops.find((s, i) => i > stopIndex && s.status === 'pending') || stops.find(s => s.status === 'pending');
          
          if(nextStop) {
              // Pequeno delay para UX
              setTimeout(() => {
                  if(confirm(`Parada concluída! Iniciar navegação para: ${nextStop.name}?`)) {
                      openNavigation(nextStop);
                  }
              }, 500);
          } else {
              alert("Rota Finalizada! Parabéns.");
          }
      }
  };

  // --- COMPUTED DATA ---
  const activeRoute = routes.find(r => r.id === activeRouteId);
  const nextPendingStop = activeRoute?.stops.find(s => s.status === 'pending');

  // --- RENDERIZADORES ---

  // 1. TELA INICIAL (LISTA DE ROTAS)
  if(view === 'home') return (
    <div className="min-h-screen pb-24 px-4 pt-4">
        <h1 className="text-2xl font-bold text-slate-800 mb-6 flex items-center gap-2">
            <Package className="text-blue-600"/> Minhas Rotas
        </h1>

        {routes.length === 0 ? (
            <div className="text-center mt-20 opacity-50">
                <p>Nenhuma rota salva.</p>
                <p className="text-sm">Clique em + para criar.</p>
            </div>
        ) : (
            <div className="space-y-3">
                {routes.map(route => {
                    const total = route.stops.length;
                    const done = route.stops.filter(s => s.status !== 'pending').length;
                    const progress = Math.round((done/total)*100);

                    return (
                        <div key={route.id} onClick={() => { setActiveRouteId(route.id); setView('details'); }} 
                             className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 active:scale-95 transition cursor-pointer relative overflow-hidden">
                            <div className="flex justify-between items-start mb-2">
                                <div>
                                    <h3 className="font-bold text-lg text-slate-800">{route.name}</h3>
                                    <p className="text-xs text-gray-400">{route.date} • {total} paradas</p>
                                </div>
                                <button onClick={(e) => { e.stopPropagation(); deleteRoute(route.id); }} className="text-gray-300 hover:text-red-500 p-2">
                                    <Trash2 size={18} />
                                </button>
                            </div>
                            
                            {/* Barra de Progresso */}
                            <div className="w-full bg-gray-100 h-2 rounded-full overflow-hidden">
                                <div className="bg-blue-600 h-full transition-all duration-500" style={{ width: `${progress}%` }}></div>
                            </div>
                            <div className="text-right text-xs font-bold text-blue-600 mt-1">{progress}% Concluído</div>
                        </div>
                    )
                })}
            </div>
        )}

        {/* Botão Flutuante Criar */}
        <button onClick={() => setView('create')} className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full fab flex items-center justify-center">
            <Plus size={32} />
        </button>
    </div>
  );

  // 2. TELA DE CRIAÇÃO
  if(view === 'create') return (
    <div className="min-h-screen bg-white p-6 flex flex-col">
        <button onClick={() => setView('home')} className="text-gray-500 mb-6 flex items-center gap-1"><ArrowLeft size={20}/> Voltar</button>
        
        <h2 className="text-2xl font-bold mb-6">Nova Rota</h2>
        
        <div className="space-y-6">
            <div>
                <label className="block text-sm font-bold text-gray-500 mb-2">NOME DA ROTA</label>
                <input 
                    type="text" 
                    placeholder="Ex: Zona Sul - Segunda" 
                    className="w-full p-4 bg-gray-50 rounded-xl border border-gray-200 focus:border-blue-500 outline-none font-medium"
                    value={newRouteName}
                    onChange={e => setNewRouteName(e.target.value)}
                />
            </div>

            <div>
                <label className="block text-sm font-bold text-gray-500 mb-2">PLANILHA DE ENDEREÇOS</label>
                <label className="w-full block cursor-pointer">
                    <div className="w-full border-2 border-dashed border-blue-200 bg-blue-50 rounded-xl p-8 flex flex-col items-center justify-center text-blue-600">
                        <Upload size={32} className="mb-2"/>
                        <span className="font-bold">Carregar Arquivo</span>
                        <span className="text-xs opacity-70">.csv ou .xlsx</span>
                    </div>
                    <input type="file" onChange={handleFileUpload} accept=".csv, .xlsx" className="hidden"/>
                </label>
            </div>

            {tempStops.length > 0 && (
                <div className="bg-green-50 p-4 rounded-xl border border-green-100 text-green-700 font-bold text-center">
                    {tempStops.length} endereços identificados!
                </div>
            )}

            <button onClick={saveNewRoute} className="w-full bg-slate-900 text-white py-4 rounded-xl font-bold text-lg shadow-lg mt-auto">
                Salvar Rota
            </button>
        </div>
    </div>
  );

  // 3. TELA DE DETALHES DA ROTA
  if(view === 'details' && activeRoute) return (
      <div className="flex flex-col h-screen bg-gray-50">
          {/* Header */}
          <div className="bg-white p-4 border-b shadow-sm sticky top-0 z-10">
              <div className="flex items-center gap-3 mb-3">
                  <button onClick={() => setView('home')}><ArrowLeft size={24} className="text-gray-600"/></button>
                  <h2 className="font-bold text-lg truncate flex-1">{activeRoute.name}</h2>
                  <button onClick={() => deleteRoute(activeRoute.id)}><Trash2 size={20} className="text-red-400"/></button>
              </div>
              
              <div className="flex gap-2">
                  <button onClick={optimizeActiveRoute} className="flex-1 bg-slate-100 text-slate-700 py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 active:bg-slate-200">
                      <Sliders size={16}/> Otimizar
                  </button>
                  {nextPendingStop && (
                      <button onClick={() => openNavigation(nextPendingStop)} className="flex-[2] bg-blue-600 text-white py-3 rounded-lg font-bold text-sm flex items-center justify-center gap-2 shadow-md animate-pulse">
                          <Navigation size={16}/> Iniciar Rota
                      </button>
                  )}
              </div>
          </div>

          {/* Lista de Paradas */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3 pb-safe">
              {activeRoute.stops.map((stop, idx) => {
                  const isNext = nextPendingStop && nextPendingStop.id === stop.id;
                  
                  return (
                      <div key={stop.id} id={`stop-${stop.id}`} 
                           className={`bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden 
                           ${stop.status === 'pending' ? 'status-pending' : stop.status === 'success' ? 'status-success' : 'status-failed'}
                           ${isNext ? 'ring-2 ring-blue-500 ring-offset-2' : ''}
                           `}>
                          
                          <div className="p-4">
                              <div className="flex justify-between items-start mb-1">
                                  <span className="font-bold text-gray-400 text-xs uppercase tracking-widest">Parada {idx + 1}</span>
                                  {stop.status === 'success' && <Check size={16} className="text-green-600"/>}
                                  {stop.status === 'failed' && <AlertTriangle size={16} className="text-red-600"/>}
                              </div>
                              
                              <h3 className="font-bold text-slate-800 text-lg mb-1">{stop.name}</h3>
                              <p className="text-gray-500 text-sm mb-4 leading-snug">{stop.address}</p>

                              {/* Ações (Só aparecem se pendente) */}
                              {stop.status === 'pending' && (
                                  <div className="grid grid-cols-2 gap-3">
                                      <button onClick={() => handleStatus(stop.id, 'failed')} className="py-3 rounded-lg border border-red-100 text-red-600 font-bold text-xs bg-red-50">
                                          NÃO ENTREGUE
                                      </button>
                                      <button onClick={() => handleStatus(stop.id, 'success')} className="py-3 rounded-lg bg-green-600 text-white font-bold text-xs shadow-md">
                                          ENTREGUE
                                      </button>
                                  </div>
                              )}
                              
                              {/* Botão Navegar Individual (Se já não foi entregue) */}
                              {stop.status === 'pending' && (
                                  <button onClick={() => openNavigation(stop)} className="w-full mt-3 py-2 text-blue-600 font-bold text-xs flex items-center justify-center gap-1 border-t border-gray-50">
                                      <Navigation size={12}/> Navegar para este local
                                  </button>
                              )}
                          </div>
                      </div>
                  );
              })}
              
              <div className="h-10"></div> {/* Espaço extra final */}
          </div>
      </div>
  );
}
