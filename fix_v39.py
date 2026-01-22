import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"update_v39_{TIMESTAMP}")

# CHAVE API
API_KEY_VALUE = "AIzaSyB8bI2MpTKfQHBTZxyPphB18TPlZ4b3ndU"

# --- CONTEÚDO DO APP.JSX ---
APP_JSX_CONTENT = """import React, { useState, useEffect, useMemo } from 'react';
import { 
  Upload, Navigation, Trash2, Plus, ArrowLeft, MapPin, 
  Package, Clock, Box, Map as MapIcon, Loader2, Search, X, List, Check, RotateCcw, Undo2, Building, Calendar, Info, DollarSign, LayoutDashboard, TrendingUp, Briefcase, Filter, AlertCircle, Fuel, Timer, Calculator, Save
} from 'lucide-react';
import { Geolocation } from '@capacitor/geolocation';
import { useJsApiLoader } from '@react-google-maps/api';
import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';

import MapView from './components/MapView';
import RouteList from './components/RouteList';

const DB_KEY = 'mp_db_v70_finance_pro';
const GOOGLE_KEY = "__API_KEY__";

const safeStr = (val) => {
    if (val === null || val === undefined) return '';
    if (typeof val === 'object') return JSON.stringify(val);
    return String(val).trim();
};

const groupStopsByStopName = (stops) => {
    if (!Array.isArray(stops)) return [];
    const groups = {};
    
    stops.forEach(stop => {
        let key;
        if (stop.stopId === null || stop.stopId === undefined) {
            key = `unique_${stop.id}`; 
        } else {
            key = stop.name ? String(stop.name).trim().toLowerCase() : 'sem_nome';
        }
        
        if (!groups[key]) {
            groups[key] = {
                id: key, 
                lat: Number(stop.lat)||0, 
                lng: Number(stop.lng)||0,
                mainName: stop.name || "Endereço", 
                mainAddress: safeStr(stop.address),
                items: [], 
                status: 'pending',
                displayOrder: stop.stopId 
            };
        }
        groups[key].items.push(stop);
        
        if (stop.stopId && (!groups[key].displayOrder || stop.stopId < groups[key].displayOrder)) {
            groups[key].displayOrder = stop.stopId;
        }
    });
    
    const ordered = [];
    const seen = new Set();
    
    stops.forEach(stop => {
        let key;
        if (stop.stopId === null || stop.stopId === undefined) {
            key = `unique_${stop.id}`;
        } else {
            key = stop.name ? String(stop.name).trim().toLowerCase() : 'sem_nome';
        }

        if (!seen.has(key)) {
            const g = groups[key];
            if (g) {
                const t = g.items.length;
                const s = g.items.filter(i => i.status === 'success').length;
                const f = g.items.filter(i => i.status === 'failed').length;
                
                if (s === t) g.status = 'success';
                else if (f === t) g.status = 'failed';
                else if (s + f === t) g.status = 'partial';
                else g.status = 'pending';

                ordered.push(g);
                seen.add(key);
            }
        }
    });
    return ordered;
};

const getProgressText = (stops) => {
    if (!stops || stops.length === 0) return "0/0";
    const done = stops.filter(s => s.status === 'success').length;
    return `${done}/${stops.length}`;
};

const calculateProgressPercent = (stops) => {
    if (!stops || stops.length === 0) return 0;
    const done = stops.filter(s => s.status === 'success').length;
    return Math.round((done / stops.length) * 100);
};

export default function App() {
  const [routes, setRoutes] = useState([]);
  const [activeRouteId, setActiveRouteId] = useState(null);
  const [view, setView] = useState('home'); 
  
  const [newRouteName, setNewRouteName] = useState('');
  const [newRouteCompany, setNewRouteCompany] = useState('');
  const [newRouteDate, setNewRouteDate] = useState(new Date().toISOString().split('T')[0]);
  const [newRouteValue, setNewRouteValue] = useState('');

  // ESTADOS DO FILTRO FINANCEIRO
  const [dashFilterType, setDashFilterType] = useState('month'); // 'all', 'month', 'week', 'day'
  const [dashFilterValue, setDashFilterValue] = useState(new Date().toISOString().slice(0, 7)); // YYYY-MM default

  // ESTADOS DO MODAL DE FINALIZAÇÃO
  const [showFinishModal, setShowFinishModal] = useState(false);
  const [finishData, setFinishData] = useState({ km: '', hours: '', expenses: '' });

  const [tempStops, setTempStops] = useState([]);
  const [importSummary, setImportSummary] = useState(null);
  const [userPos, setUserPos] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [toast, setToast] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showMap, setShowMap] = useState(false);
  const [directionsResponse, setDirectionsResponse] = useState(null);
  
  const [realMetrics, setRealMetrics] = useState({ dist: '0 km', time: '0 min' });

  const [isReordering, setIsReordering] = useState(false);
  const [reorderList, setReorderList] = useState([]); 

  const { isLoaded } = useJsApiLoader({ id: 'google-map-script', googleMapsApiKey: GOOGLE_KEY });

  // --- 1. DASHBOARD INTELIGENTE (ITEM 1, 2, 4) ---
  const dashboardStats = useMemo(() => {
      let filtered = routes;

      // Lógica de Filtro (Item 2)
      if (dashFilterType === 'month' && dashFilterValue) {
          filtered = routes.filter(r => r.date.startsWith(dashFilterValue));
      } else if (dashFilterType === 'day' && dashFilterValue) {
          filtered = routes.filter(r => r.date === dashFilterValue);
      } else if (dashFilterType === 'week' && dashFilterValue) {
           // Lógica simplificada de semana (pega a string 2024-W32)
           // Para simplificar no React sem libs pesadas, vamos filtrar os últimos 7 dias da data selecionada se fosse date, 
           // mas input type week retorna "2024-W01".
           // Vamos fazer um filtro simples: se o input type week estiver setado.
           // (Implementação robusta de semana requer momentjs ou similar, aqui faremos string compare simples ou 'all' fallback por enquanto)
           // Para não complicar, se for semana, mostra tudo (TODO: refinar logica de semana)
           filtered = routes; 
      }

      // Ordenação Cronológica (Item 1: Antigo -> Novo na Direita)
      filtered.sort((a, b) => new Date(a.date) - new Date(b.date));

      let totalRevenue = 0;
      let totalExpenses = 0;
      let totalKmDriven = 0;
      let totalHours = 0;
      let totalSuccess = 0;
      let totalStops = 0;

      const graphData = filtered.map(r => {
          const val = parseFloat(r.value || 0);
          const exp = parseFloat(r.expenses || 0);
          const km = parseFloat(r.realKm || 0);
          const hrs = parseFloat(r.hours || 0);

          totalRevenue += val;
          totalExpenses += exp;
          totalKmDriven += km;
          totalHours += hrs;

          if (r.stops) {
              totalStops += r.stops.length;
              totalSuccess += r.stops.filter(s => s.status === 'success').length;
          }

          return {
              date: new Date(r.date).toLocaleDateString('pt-BR', {day:'2-digit', month:'2-digit'}),
              faturamento: val,
              lucro: val - exp
          };
      });

      const netProfit = totalRevenue - totalExpenses;
      const profitMargin = totalRevenue > 0 ? ((netProfit / totalRevenue) * 100).toFixed(1) : 0;
      const earningsPerKm = totalKmDriven > 0 ? (totalRevenue / totalKmDriven).toFixed(2) : "0.00";
      const earningsPerHour = totalHours > 0 ? (totalRevenue / totalHours).toFixed(2) : "0.00";
      const avgRoute = filtered.length > 0 ? (totalRevenue / filtered.length).toFixed(2) : "0.00";
      const successRate = totalStops > 0 ? Math.round((totalSuccess / totalStops) * 100) : 0;

      return {
          totalRevenue: totalRevenue.toFixed(2),
          totalExpenses: totalExpenses.toFixed(2),
          netProfit: netProfit.toFixed(2),
          profitMargin,
          earningsPerKm,
          earningsPerHour,
          avgRoute,
          successRate,
          totalSuccess,
          graphData,
          count: filtered.length
      };
  }, [routes, dashFilterType, dashFilterValue]);

  useEffect(() => {
    try {
        const saved = localStorage.getItem(DB_KEY);
        if (saved) setRoutes(JSON.parse(saved));
    } catch (e) {}
    getCurrentLocation(true); 
  }, []);

  useEffect(() => { localStorage.setItem(DB_KEY, JSON.stringify(routes)); }, [routes]);

  const showToast = (msg, type = 'success') => {
      setToast({ msg, type });
      setTimeout(() => setToast(null), 2000);
  };

  const getCurrentLocation = async (silent = false) => {
      try {
          const pos = await Geolocation.getCurrentPosition({ enableHighAccuracy: true });
          const p = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserPos(p);
          return p;
      } catch (e) {
          if (!silent) alert("Erro ao obter GPS: " + e.message);
          return null;
      }
  };

  const ensurePermissionAndPos = async () => {
      if (userPos) return userPos;
      if (confirm("O App precisa acessar sua localização para o mapa. Permitir?")) {
          return await getCurrentLocation(false);
      }
      return null;
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    const processData = (d, isBin) => {
        let data = [];
        try {
            if(isBin) {
                const wb = XLSX.read(d, {type:'binary'});
                data = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]]);
            } else {
                data = Papa.parse(d, {header:true, skipEmptyLines:true}).data;
            }
        } catch(err) { return alert("Arquivo inválido."); }

        const norm = data.map((r, i) => {
            const k = {};
            Object.keys(r).forEach(key => k[String(key).trim().toLowerCase()] = r[key]);
            
            const name = safeStr(k['stop'] || k['parada'] || k['cliente'] || k['nome'] || k['razao social'] || `Parada ${i+1}`);
            const address = safeStr(k['destination address'] || k['endereço'] || k['endereco'] || k['rua'] || '---');
            
            let stopId = null;
            const stopVal = k['stop'] || k['seq'] || k['ordem'] || k['sequence'];
            if (stopVal) {
                const parsed = parseInt(stopVal);
                if (!isNaN(parsed)) stopId = parsed;
            }

            return {
                id: Date.now() + i + Math.random(),
                name: name,
                stopId: stopId,
                recipient: safeStr(k['recebedor'] || k['contato'] || k['destinatario'] || 'Recebedor'),
                address: address,
                lat: parseFloat(k['latitude'] || k['lat'] || 0),
                lng: parseFloat(k['longitude'] || k['long'] || k['lng'] || 0),
                status: 'pending'
            };
        }).filter(i => i.lat !== 0);
        
        if (norm.some(i => i.stopId !== null)) {
            norm.sort((a, b) => (a.stopId || 9999) - (b.stopId || 9999));
        }

        if (norm.length > 0) {
            setTempStops(norm);
            setImportSummary({ count: norm.length, first: norm[0].address });
        }
    };
    if(file.name.endsWith('.csv')) { reader.onload = e => processData(e.target.result, false); reader.readAsText(file); }
    else { reader.onload = e => processData(e.target.result, true); reader.readAsBinaryString(file); }
  };

  const createRoute = () => {
      if(!newRouteName.trim() || !tempStops.length) return;
      setRoutes([{ 
          id: Date.now(), 
          name: newRouteName, 
          company: newRouteCompany, 
          date: newRouteDate, 
          value: newRouteValue, 
          stops: tempStops, 
          optimized: true,
          expenses: 0, // Novo campo
          realKm: 0,   // Novo campo
          hours: 0     // Novo campo
      }, ...routes]);
      
      setNewRouteName(''); 
      setNewRouteCompany('');
      setNewRouteDate(new Date().toISOString().split('T')[0]);
      setNewRouteValue('');
      setTempStops([]); 
      setImportSummary(null); 
      setView('home');
  };

  const deleteRoute = () => {
      if (!activeRouteId) return;
      if (confirm("ATENÇÃO: Deseja apagar esta rota permanentemente?")) {
          const updated = routes.filter(r => r.id !== activeRouteId);
          setRoutes(updated);
          setView('home');
          setActiveRouteId(null);
      }
  };

  const resetRoute = () => {
      if (!activeRouteId) return;
      if (confirm("Reiniciar todo o progresso?")) {
          const rIdx = routes.findIndex(r => r.id === activeRouteId);
          const updated = [...routes];
          updated[rIdx].stops = updated[rIdx].stops.map(s => ({...s, status: 'pending'}));
          setRoutes(updated);
          showToast("Rota reiniciada!", "info");
      }
  };

  // --- ITEM 3: FINALIZAR ROTA COM RELATÓRIO ---
  const openFinishModal = () => {
      setShowFinishModal(true);
      // Preenche com valores atuais se já existirem
      const r = routes.find(ro => ro.id === activeRouteId);
      if (r) {
          setFinishData({
              km: r.realKm || '',
              hours: r.hours || '',
              expenses: r.expenses || ''
          });
      }
  };

  const saveFinishData = () => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const updated = [...routes];
      updated[rIdx] = {
          ...updated[rIdx],
          realKm: finishData.km,
          hours: finishData.hours,
          expenses: finishData.expenses,
          isFinished: true // Marca flag
      };

      setRoutes(updated);
      setShowFinishModal(false);
      showToast("Rota Finalizada e Dados Salvos!", "success");
      setView('home'); // Volta pra home com sensação de dever cumprido
  };

  const updateAddress = async (stopId, newAddress) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const updatedRoutes = [...routes];
      const stopIndex = updatedRoutes[rIdx].stops.findIndex(s => s.id === stopId);
      if (stopIndex !== -1) {
          updatedRoutes[rIdx].stops[stopIndex].address = newAddress;
          setRoutes(updatedRoutes);
          try {
              const response = await fetch(`https://maps.googleapis.com/maps/api/geocode/json?address=${encodeURIComponent(newAddress)}&key=${GOOGLE_KEY}`);
              const data = await response.json();
              if (data.status === 'OK' && data.results.length > 0) {
                  const loc = data.results[0].geometry.location;
                  updatedRoutes[rIdx].stops[stopIndex].lat = loc.lat;
                  updatedRoutes[rIdx].stops[stopIndex].lng = loc.lng;
                  setRoutes(updatedRoutes); 
                  showToast("Endereço e Mapa Atualizados!");
              } else {
                  showToast("Texto atualizado (Mapa não achou)", "info");
              }
          } catch(e) { console.error(e); }
      }
  };

  const startReorderMode = () => {
      handleToggleMap(); 
      setIsReordering(true);
      setReorderList([]); 
      showToast("Toque nos pinos na ordem desejada!", "info");
  };

  const handleMapMarkerClick = (groupId) => {
      if (!isReordering) return;
      if (reorderList.includes(groupId)) return;
      setReorderList(prev => [...prev, groupId]);
  };

  const undoLastSelection = () => {
      if (reorderList.length === 0) return;
      setReorderList(prev => prev.slice(0, -1));
  };

  const saveReorder = () => {
      if (!isReordering) return;
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;

      const currentStops = [...routes[rIdx].stops];
      const groups = groupStopsByStopName(currentStops);
      
      if (reorderList.length < groups.length) {
          const diff = groups.length - reorderList.length;
          alert(`Você precisa selecionar todas as paradas! Faltam ${diff}.`);
          return;
      }
      
      let newStopsList = [];
      reorderList.forEach(groupId => {
          const group = groups.find(g => g.id === groupId);
          if (group) newStopsList.push(...group.items);
      });

      const updatedRoutes = [...routes];
      updatedRoutes[rIdx].stops = newStopsList;
      setRoutes(updatedRoutes);
      
      setIsReordering(false);
      setReorderList([]);
      showToast("Nova sequência salva!");
  };

  const cancelReorder = () => {
      setIsReordering(false);
      setReorderList([]);
      setShowMap(false);
  };

  const setStatus = (stopId, status) => {
      const rIdx = routes.findIndex(r => r.id === activeRouteId);
      if (rIdx === -1) return;
      const updatedRoutes = [...routes];
      const route = updatedRoutes[rIdx];
      const stopIndex = route.stops.findIndex(s => s.id === stopId);
      if (stopIndex !== -1) {
          route.stops[stopIndex].status = status;
          setRoutes(updatedRoutes);
          if (status === 'success') showToast("Pacote Entregue!");
      }
  };

  const setAllStatus = (items, status) => {
      items.forEach(item => setStatus(item.id, status));
  };

  const startRoute = async (lat, lng) => {
      await ensurePermissionAndPos(); 
      window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}&travelmode=driving`, '_system');
  };

  const handleToggleMap = async () => {
      if (!showMap) {
          await ensurePermissionAndPos();
      }
      setShowMap(!showMap);
  };

  const handleBack = () => {
      if (showMap) {
          if (isReordering) {
              if(confirm("Sair da edição sem salvar?")) cancelReorder();
          } else {
              setShowMap(false);
          }
      } else {
          setView('home');
      }
  };

  const toggleGroup = (id) => setExpandedGroups(prev => ({...prev, [id]: !prev[id]}));

  const activeRoute = routes.find(r => r.id === activeRouteId);
  const groupedStops = useMemo(() => activeRoute ? groupStopsByStopName(activeRoute.stops) : [], [activeRoute, routes]);
  const nextGroup = groupedStops.find(g => g.status === 'pending' || g.status === 'partial');
  
  // Verifica se está 100% concluído para mostrar botão de finalizar
  const isRouteComplete = activeRoute && !nextGroup;

  useEffect(() => {
      if (isLoaded && nextGroup && userPos) {
          const service = new window.google.maps.DirectionsService();
          service.route({
              origin: userPos,
              destination: { lat: nextGroup.lat, lng: nextGroup.lng },
              travelMode: 'DRIVING'
          }, (res, status) => {
              if (status === 'OK') {
                  setDirectionsResponse(res);
                  const route = res.routes[0];
                  let totalDist = 0;
                  let totalDur = 0;
                  if (route.legs) {
                      route.legs.forEach(leg => {
                          totalDist += leg.distance.value;
                          totalDur += leg.duration.value;
                      });
                      const km = (totalDist / 1000).toFixed(1) + " km";
                      const hours = Math.floor(totalDur / 3600);
                      const mins = Math.floor((totalDur % 3600) / 60);
                      const time = (hours > 0 ? `${hours}h ` : "") + `${mins}min`;
                      setRealMetrics({ dist: km, time: time });
                  }
              }
          });
      } else {
          setDirectionsResponse(null);
          setRealMetrics({ dist: '0 km', time: '0 min' });
      }
  }, [nextGroup?.id, userPos, isLoaded]);

  // --- DASHBOARD VIEW (FILTROS DINÂMICOS) ---
  if (view === 'dashboard') return (
      <div className="min-h-screen bg-slate-50 flex flex-col pt-12">
          <div className="bg-white p-6 shadow-sm z-10">
              <button onClick={() => setView('home')} className="mb-4 text-slate-400 hover:text-slate-600"><ArrowLeft/></button>
              <h2 className="text-2xl font-bold text-slate-900">Financeiro</h2>
              <p className="text-sm text-slate-500">Gestão de Ganhos e Custos</p>
              
              {/* FILTROS INTELIGENTES */}
              <div className="flex gap-2 mt-4 items-center overflow-x-auto pb-2">
                  <button onClick={() => setDashFilterType('all')} className={`px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap ${dashFilterType==='all' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500'}`}>
                      Geral
                  </button>
                  <button onClick={() => {setDashFilterType('month'); setDashFilterValue(new Date().toISOString().slice(0, 7))}} className={`px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap ${dashFilterType==='month' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500'}`}>
                      Mês
                  </button>
                  <button onClick={() => {setDashFilterType('day'); setDashFilterValue(new Date().toISOString().split('T')[0])}} className={`px-4 py-2 rounded-full text-xs font-bold transition whitespace-nowrap ${dashFilterType==='day' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-500'}`}>
                      Dia
                  </button>
                  
                  {/* INPUT CONDICIONAL DE DATA */}
                  {dashFilterType === 'month' && (
                      <input type="month" className="bg-slate-100 rounded-lg px-2 py-1 text-xs border border-slate-200 outline-none" value={dashFilterValue} onChange={e => setDashFilterValue(e.target.value)} />
                  )}
                  {dashFilterType === 'day' && (
                      <input type="date" className="bg-slate-100 rounded-lg px-2 py-1 text-xs border border-slate-200 outline-none" value={dashFilterValue} onChange={e => setDashFilterValue(e.target.value)} />
                  )}
              </div>
          </div>

          <div className="flex-1 p-6 space-y-4 overflow-y-auto">
              
              {/* CARDS INTELIGENTES (ITEM 4) */}
              <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-900 p-4 rounded-2xl shadow-lg text-white col-span-2">
                      <div className="flex items-center gap-2 opacity-80 mb-1"><DollarSign size={16}/><span className="text-xs font-bold uppercase">Lucro Líquido</span></div>
                      <div className="text-3xl font-bold">R$ {dashboardStats.netProfit}</div>
                      <div className="text-[10px] opacity-60 mt-1">Margem: {dashboardStats.profitMargin}% (Rec: {dashboardStats.totalRevenue} - Desp: {dashboardStats.totalExpenses})</div>
                  </div>

                  <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                      <div className="flex items-center gap-2 text-slate-400 mb-1"><MapPin size={16}/><span className="text-xs font-bold uppercase">R$ / Km</span></div>
                      <div className="text-xl font-bold text-blue-600">R$ {dashboardStats.earningsPerKm}</div>
                  </div>
                  <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                      <div className="flex items-center gap-2 text-slate-400 mb-1"><Clock size={16}/><span className="text-xs font-bold uppercase">R$ / Hora</span></div>
                      <div className="text-xl font-bold text-green-600">R$ {dashboardStats.earningsPerHour}</div>
                  </div>
                  
                  <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                      <div className="flex items-center gap-2 text-slate-400 mb-1"><Check size={16}/><span className="text-xs font-bold uppercase">Entregues</span></div>
                      <div className="text-xl font-bold text-slate-800">{dashboardStats.totalSuccess}</div>
                  </div>
                  <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100">
                      <div className="flex items-center gap-2 text-slate-400 mb-1"><TrendingUp size={16}/><span className="text-xs font-bold uppercase">Sucesso</span></div>
                      <div className="text-xl font-bold text-slate-800">{dashboardStats.successRate}%</div>
                  </div>
              </div>

              {/* GRÁFICO (ORDEM CORRIGIDA) */}
              {dashboardStats.graphData.length > 0 && (
                  <div className="bg-white p-4 rounded-2xl shadow-sm border border-slate-100 h-72">
                      <h3 className="text-xs font-bold text-slate-500 mb-4 uppercase flex items-center gap-2"><LayoutDashboard size={14}/> Performance Recente</h3>
                      <ResponsiveContainer width="100%" height="85%">
                          <BarChart data={dashboardStats.graphData}>
                              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E2E8F0"/>
                              <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{fontSize: 10, fill: '#94A3B8'}} dy={10}/>
                              <Tooltip cursor={{fill: '#F8FAFC'}} contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)'}}/>
                              <Legend iconType="circle" wrapperStyle={{fontSize:'10px', paddingTop:'10px'}}/>
                              <Bar name="Faturamento" dataKey="faturamento" fill="#3B82F6" radius={[4, 4, 0, 0]} barSize={12}/>
                              <Bar name="Lucro Real" dataKey="lucro" fill="#10B981" radius={[4, 4, 0, 0]} barSize={12}/>
                          </BarChart>
                      </ResponsiveContainer>
                  </div>
              )}
          </div>
      </div>
  );

  if (view === 'home') return (
      <div className="min-h-screen pb-24 px-6 pt-12 bg-slate-100">
          <div className="flex justify-between items-center mb-8">
              <div>
                  <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Minhas Rotas</h1>
                  <p className="text-slate-500 text-sm mt-1">Gerencie suas entregas</p>
              </div>
              <div className="flex gap-2">
                  <button onClick={() => setView('dashboard')} className="bg-white p-3 rounded-2xl shadow-sm text-slate-600 hover:text-blue-600 transition"><LayoutDashboard size={24}/></button>
              </div>
          </div>
          {routes.length === 0 ? (
              <div className="text-center mt-32 opacity-40 flex flex-col items-center">
                  <div className="bg-white p-6 rounded-full shadow-sm mb-4"><MapIcon size={48} className="text-slate-300"/></div>
                  <p className="font-bold text-slate-400">Nenhuma rota criada</p>
              </div>
          ) : (
              <div className="space-y-5">
                  {routes.map(r => {
                      const done = r.stops.filter(s => s.status === 'success').length;
                      const percent = calculateProgressPercent(r.stops);
                      
                      return (
                          <div key={r.id} onClick={() => { setActiveRouteId(r.id); setView('details'); }} className="bg-white p-5 rounded-2xl shadow-sm border border-slate-100 active:scale-[0.98] transition-transform duration-200">
                              <div className="flex justify-between items-start mb-3">
                                  <div>
                                      <h3 className="font-bold text-lg text-slate-800">{safeStr(r.name)}</h3>
                                      <p className="text-xs text-slate-400 font-medium mt-0.5 uppercase tracking-wider">{r.company || 'Empresa não informada'}</p>
                                  </div>
                                  <div className="text-right">
                                      <div className="bg-slate-100 px-2 py-1 rounded text-[10px] font-bold text-slate-500 mb-1">{new Date(r.date || r.id).toLocaleDateString()}</div>
                                      {r.value && <div className="text-green-600 font-bold text-xs">R$ {r.value}</div>}
                                  </div>
                              </div>
                              
                              <div className="flex items-center gap-4 mb-4">
                                  <div className="flex-1">
                                      <div className="flex justify-between text-xs font-bold text-slate-600 mb-1">
                                          <span>Progresso</span>
                                          <span>{done}/{r.stops.length}</span>
                                      </div>
                                      <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                                          <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{width: `${percent}%`}}></div>
                                      </div>
                                  </div>
                              </div>
                          </div>
                      )
                  })}
              </div>
          )}
          <button onClick={() => setView('create')} className="fixed bottom-8 right-8 w-16 h-16 rounded-full bg-slate-900 text-white shadow-2xl flex items-center justify-center hover:bg-slate-800 transition active:scale-90">
              <Plus size={32}/>
          </button>
      </div>
  );

  if (view === 'create') return (
      <div className="min-h-screen bg-slate-50 flex flex-col pt-12">
          <div className="bg-white p-6 pb-4 shadow-sm z-10">
              <button onClick={() => setView('home')} className="mb-4 text-slate-400 hover:text-slate-600"><ArrowLeft/></button>
              <h2 className="text-2xl font-bold text-slate-900">Nova Rota</h2>
              <p className="text-sm text-slate-500">Preencha os dados para iniciar</p>
          </div>

          <div className="flex-1 p-6 space-y-6 overflow-y-auto">
              <div className="space-y-4">
                  <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Nome da Rota</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><MapIcon className="text-slate-300 mr-3" size={20}/><input type="text" className="flex-1 outline-none text-sm font-medium" placeholder="Ex: Rota Zona Sul" value={newRouteName} onChange={e => setNewRouteName(e.target.value)}/></div></div>
                  <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Empresa</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><Building className="text-slate-300 mr-3" size={20}/><input type="text" className="flex-1 outline-none text-sm font-medium" placeholder="Ex: Mercado Livre" value={newRouteCompany} onChange={e => setNewRouteCompany(e.target.value)}/></div></div>
                  
                  <div className="grid grid-cols-2 gap-4">
                      <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Data</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><Calendar className="text-slate-300 mr-3" size={20}/><input type="date" className="flex-1 outline-none text-sm font-medium" value={newRouteDate} onChange={e => setNewRouteDate(e.target.value)}/></div></div>
                      <div><label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Valor (R$)</label><div className="flex items-center bg-white p-4 rounded-xl border border-slate-200 focus-within:border-blue-500 transition"><DollarSign className="text-slate-300 mr-1" size={20}/><input type="number" className="flex-1 outline-none text-sm font-medium" placeholder="0,00" value={newRouteValue} onChange={e => setNewRouteValue(e.target.value)}/></div></div>
                  </div>
              </div>

              <div>
                  <label className="text-xs font-bold text-slate-500 uppercase ml-1 mb-1 block">Arquivo de Importação</label>
                  {!importSummary ? (
                      <label className="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed border-blue-200 bg-blue-50/50 rounded-2xl cursor-pointer hover:bg-blue-50 transition"><Upload className="mb-2 text-blue-500"/><span className="text-sm font-bold text-blue-600">Toque para Selecionar (CSV/XLSX)</span><input type="file" onChange={handleFileUpload} className="hidden" accept=".csv,.xlsx"/></label>
                  ) : (
                      <div className="w-full bg-green-50 border border-green-200 rounded-2xl p-6 text-center animate-in fade-in zoom-in"><div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-3"><Check className="text-green-600" size={24}/></div><h3 className="text-green-800 font-bold text-lg">Arquivo Carregado!</h3><p className="text-green-600 mt-1 text-sm">{importSummary.count} pacotes encontrados</p><p className="text-green-500/70 text-xs mt-1 truncate px-4">{importSummary.first}...</p><button onClick={() => {setImportSummary(null); setTempStops([]);}} className="text-xs text-red-400 mt-4 font-bold hover:underline">REMOVER ARQUIVO</button></div>
                  )}
              </div>
          </div>
          <div className="p-6 bg-white border-t border-slate-100"><button onClick={createRoute} disabled={!importSummary || !newRouteName} className={`w-full py-4 rounded-xl font-bold text-lg shadow-lg transition-all ${importSummary && newRouteName ? 'bg-slate-900 text-white hover:bg-slate-800' : 'bg-slate-100 text-slate-400'}`}>Criar Rota</button></div>
      </div>
  );

  return (
      <div className="flex flex-col h-screen bg-slate-50 relative">
          {toast && <div className={`fixed top-4 left-4 right-4 p-4 rounded-xl shadow-2xl z-50 text-white text-center font-bold text-sm toast-anim ${toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'}`}>{toast.msg}</div>}
          
          {/* MODAL DE FINALIZAÇÃO DA ROTA (ITEM 3) */}
          {showFinishModal && (
              <div className="absolute inset-0 z-[3000] bg-black/60 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 animate-in fade-in duration-200">
                  <div className="bg-white w-full sm:max-w-sm rounded-t-3xl sm:rounded-3xl p-6 shadow-2xl animate-in slide-in-from-bottom-10">
                      <div className="flex justify-between items-center mb-6">
                        <h3 className="text-xl font-bold flex items-center gap-2 text-slate-900">
                            <CheckCircle size={24} className="text-green-500"/> Finalizar Rota
                        </h3>
                        <button onClick={() => setShowFinishModal(false)} className="text-slate-400 bg-slate-100 p-2 rounded-full"><X size={20}/></button>
                      </div>
                      
                      <div className="space-y-4 mb-8">
                          <div>
                              <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">KM Final (Rodados)</label>
                              <div className="flex items-center bg-slate-50 p-4 rounded-2xl border border-slate-200 focus-within:border-blue-500 focus-within:ring-2 focus-within:ring-blue-100 transition">
                                  <MapPin className="text-slate-400 mr-3" size={20}/>
                                  <input type="number" className="flex-1 outline-none text-lg font-bold bg-transparent" placeholder="0" value={finishData.km} onChange={e => setFinishData({...finishData, km: e.target.value})}/>
                                  <span className="text-sm font-bold text-slate-400">km</span>
                              </div>
                          </div>

                          <div className="flex gap-4">
                              <div className="flex-1">
                                  <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Horas</label>
                                  <div className="flex items-center bg-slate-50 p-4 rounded-2xl border border-slate-200 focus-within:border-blue-500 transition">
                                      <Timer className="text-slate-400 mr-2" size={20}/>
                                      <input type="number" className="flex-1 outline-none text-lg font-bold bg-transparent" placeholder="0" value={finishData.hours} onChange={e => setFinishData({...finishData, hours: e.target.value})}/>
                                  </div>
                              </div>
                              <div className="flex-1">
                                  <label className="text-[10px] font-bold text-slate-400 uppercase mb-1 block">Gastos (R$)</label>
                                  <div className="flex items-center bg-slate-50 p-4 rounded-2xl border border-slate-200 focus-within:border-blue-500 transition">
                                      <Fuel className="text-slate-400 mr-2" size={20}/>
                                      <input type="number" className="flex-1 outline-none text-lg font-bold bg-transparent" placeholder="0" value={finishData.expenses} onChange={e => setFinishData({...finishData, expenses: e.target.value})}/>
                                  </div>
                              </div>
                          </div>
                      </div>

                      <button onClick={saveFinishData} className="w-full bg-gradient-to-r from-yellow-500 to-amber-600 text-white py-4 rounded-2xl font-bold text-lg shadow-xl shadow-amber-200 active:scale-95 transition flex items-center justify-center gap-2">
                          <Save size={20}/> Confirmar & Relatar
                      </button>
                  </div>
              </div>
          )}

          {isReordering && (
              <div className="absolute bottom-0 left-0 right-0 bg-yellow-400 px-4 py-3 z-50 flex items-center justify-between shadow-[0_-4px_10px_rgba(0,0,0,0.1)] rounded-t-2xl animate-in slide-in-from-bottom-4">
                  <div className="flex flex-col">
                      <span className="text-[10px] font-bold text-black/60 uppercase tracking-wider">Sequência</span>
                      <span className="text-lg font-extrabold text-black leading-none">{reorderList.length} Pinos</span>
                  </div>
                  <div className="flex gap-2">
                      <button onClick={undoLastSelection} className="bg-white/80 h-9 px-3 rounded-lg text-black font-bold flex items-center gap-1 active:scale-95 text-xs"><Undo2 size={14}/> Desfazer</button>
                      <button onClick={cancelReorder} className="bg-white/50 h-9 px-3 rounded-lg text-xs font-bold active:scale-95 text-black">Sair</button>
                      <button onClick={saveReorder} className="bg-black text-white h-9 px-4 rounded-lg text-xs font-bold shadow-lg active:scale-95">SALVAR</button>
                  </div>
              </div>
          )}

          <div className="bg-white px-5 py-4 shadow-sm z-20 sticky top-0 rounded-b-3xl">
              <div className="flex items-center justify-between mb-3">
                  <button onClick={handleBack} className="p-2 -ml-2 rounded-full hover:bg-slate-100"><ArrowLeft className="text-slate-600"/></button>
                  <div className="text-center">
                      <h2 className="font-bold text-slate-900 leading-tight">{safeStr(activeRoute.name)}</h2>
                      <p className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">{activeRoute.company || 'Rota'}</p>
                  </div>
                  <div className="text-right">
                      {activeRoute.value && <span className="block text-xs font-bold text-green-600">R$ {activeRoute.value}</span>}
                      <span className="text-[10px] text-slate-400 font-bold">{getProgressText(activeRoute.stops)}</span>
                  </div>
              </div>
              
              <div className="flex gap-2">
                  <button onClick={resetRoute} className="p-3 bg-slate-50 rounded-xl text-slate-500 shadow-sm flex-1 flex justify-center"><RotateCcw size={20}/></button>
                  <button onClick={deleteRoute} className="p-3 bg-red-50 rounded-xl text-red-500 shadow-sm flex-1 flex justify-center"><Trash2 size={20}/></button>
                  <button onClick={handleToggleMap} className={`p-3 rounded-xl shadow-sm flex-1 flex justify-center ${showMap ? 'bg-blue-100 text-blue-600' : 'bg-slate-900 text-white'}`}>
                      {showMap ? <List size={20}/> : <MapIcon size={20}/>}
                  </button>
              </div>

              {!showMap && (
                  <div className="relative mt-3">
                      <Search size={16} className="absolute left-3 top-3 text-slate-400"/>
                      <input type="text" placeholder="Buscar parada..." className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-100 text-sm font-medium outline-none" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}/>
                      {searchQuery && <button onClick={() => setSearchQuery('')} className="absolute right-3 top-3 text-slate-400"><X size={16}/></button>}
                  </div>
              )}
          </div>

          {showMap ? (
              <div className="flex-1 relative bg-slate-100">
                  <MapView 
                      userPos={userPos} 
                      groupedStops={groupedStops} 
                      directionsResponse={directionsResponse}
                      nextGroup={nextGroup}
                      openNav={startRoute} 
                      isLoaded={isLoaded}
                      setStatus={setStatus}
                      setAllStatus={setAllStatus}
                      isReordering={isReordering}
                      reorderList={reorderList}
                      onMarkerClick={handleMapMarkerClick}
                      onStartReorder={startReorderMode} 
                  />
                  {!isReordering && nextGroup && (
                      <div className="absolute bottom-6 left-6 right-6">
                          <button onClick={() => startRoute(nextGroup.lat, nextGroup.lng)} className="w-full py-4 rounded-2xl font-bold text-lg flex items-center justify-center gap-3 text-white shadow-2xl bg-green-600 animate-in slide-in-from-bottom-4">
                              <Navigation size={20}/> Iniciar Rota
                          </button>
                      </div>
                  )}
              </div>
          ) : (
              <RouteList 
                  groupedStops={groupedStops}
                  nextGroup={nextGroup}
                  activeRoute={activeRoute}
                  searchQuery={searchQuery}
                  expandedGroups={expandedGroups}
                  toggleGroup={toggleGroup}
                  setStatus={setStatus}
                  onStartReorder={startReorderMode}
                  onEditAddress={updateAddress}
              />
          )}

          {/* BOTÃO FLUTUANTE DE FINALIZAR ROTA (APENAS SE 100% COMPLETO) */}
          {!showMap && isRouteComplete && !activeRoute.isFinished && (
              <div className="fixed bottom-6 left-6 right-6 animate-in slide-in-from-bottom-10">
                   <button onClick={openFinishModal} className="w-full bg-gradient-to-r from-amber-400 to-orange-500 text-white py-4 rounded-2xl font-extrabold text-lg shadow-2xl shadow-orange-300 flex items-center justify-center gap-2">
                       <CheckCircle size={24}/> FINALIZAR & RELATAR
                   </button>
              </div>
          )}
      </div>
  );
}
"""

FILES_TO_WRITE = {
    "src/App.jsx": APP_JSX_CONTENT.replace("__API_KEY__", API_KEY_VALUE)
}

def write_files():
    for path, content in FILES_TO_WRITE.items():
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Escrevendo {path}")

def main():
    print(f"--- Iniciando V39 (Finance Pro + Finish) {TIMESTAMP} ---")
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    if os.path.exists("src/App.jsx"): shutil.copy2("src/App.jsx", CURRENT_BACKUP_PATH)

    write_files()

    print("--- Git Push ---")
    subprocess.run("git add .", shell=True)
    subprocess.run(f'git commit -m "Update V39: Finance Pro & Route Finish - {TIMESTAMP}"', shell=True)
    subprocess.run("git push", shell=True)
    
    os.remove(__file__)
    print("Concluído.")

if __name__ == "__main__":
    main()


