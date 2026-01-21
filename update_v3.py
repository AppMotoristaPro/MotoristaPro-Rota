import os
import shutil
import datetime
import subprocess

# --- CONFIGURAÇÕES ---
BACKUP_DIR = "backup"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
CURRENT_BACKUP_PATH = os.path.join(BACKUP_DIR, f"evolucao_v3_{TIMESTAMP}")

FILES_TO_WRITE = {
    # ATUALIZAÇÃO DO COMPONENTE DE LISTA (Itens 2, 3 e 7 do arquivo)
    "src/components/RouteList.jsx": """import React from 'react';
import { Check, ChevronUp, ChevronDown, Layers } from 'lucide-react';

export default function RouteList({ 
    groupedStops, 
    nextGroup, 
    activeRoute, 
    searchQuery, 
    expandedGroups, 
    toggleGroup, 
    setStatus 
}) {
    const safeStr = (val) => val ? String(val).trim() : '';

    // Função para marcar todos de um grupo como entregues (Item 3)
    const setAllStatus = (items, status) => {
        items.forEach(item => {
            if (item.status === 'pending') setStatus(item.id, status);
        });
    };

    const filteredGroups = !searchQuery ? groupedStops : groupedStops.filter(g => 
        safeStr(g.mainName).toLowerCase().includes(searchQuery.toLowerCase()) || 
        safeStr(g.mainAddress).toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
            {/* DESTAQUE (Item 2) */}
            {!searchQuery && nextGroup && activeRoute.optimized && (
                <div className="modern-card p-6 border-l-8 border-blue-600 bg-white relative mb-6 shadow-lg">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">ALVO ATUAL</div>
                    <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                    <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                    
                    {nextGroup.items.filter(i => i.status === 'pending').length > 1 && (
                        <button 
                            onClick={() => setAllStatus(nextGroup.items, 'success')}
                            className="w-full mb-4 py-2 bg-green-100 text-green-700 rounded-lg text-xs font-bold flex items-center justify-center gap-2"
                        >
                            <Layers size={14}/> ENTREGAR TODOS ({nextGroup.items.filter(i => i.status === 'pending').length})
                        </button>
                    )}

                    <div className="space-y-3 border-t border-slate-100 pt-3">
                        {nextGroup.items.map((item, idx) => (
                            item.status === 'pending' && (
                                <div key={item.id} className="bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <span className="text-[10px] font-bold text-slate-400 block mb-1">VOLUME #{idx + 1}</span>
                                    <p className="text-sm font-bold text-slate-800 mb-3">{item.address}</p>
                                    <div className="flex gap-2">
                                        <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-3 bg-white border border-red-200 text-red-600 rounded-xl text-xs font-bold">FALHA</button>
                                        <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-3 bg-green-600 text-white rounded-xl text-xs font-bold shadow-md">ENTREGUE</button>
                                    </div>
                                </div>
                            )
                        ))}
                    </div>
                </div>
            )}

            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Sequência da Rota</h4>
            {filteredGroups.map((group, idx) => (
                (!searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) ? null : (
                    <div key={group.id} className={`modern-card border-l-4 ${group.status === 'success' ? 'border-green-500 opacity-60' : 'border-slate-200'}`}>
                        <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                            <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center font-bold text-xs">
                                {group.status === 'success' ? <Check size={14} className="text-green-600"/> : (idx + 1)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                <p className="text-xs text-slate-400 truncate">{group.items.length} pacote(s)</p>
                            </div>
                            {group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp/> : <ChevronDown/>) : null}
                        </div>
                    </div>
                )
            ))}
        </div>
    );
}
""",

    # ATUALIZAÇÃO DO MAPA (Item 6 e 8)
    "src/components/MapView.jsx": """import React, { useState } from 'react';
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
"""
}

def run_command(cmd):
    try:
        subprocess.run(cmd, check=True, shell=True)
    except Exception as e:
        print(f"Erro no comando {cmd}: {e}")

def main():
    print(f"--- Backup em {CURRENT_BACKUP_PATH} ---")
    if not os.path.exists(BACKUP_DIR): os.makedirs(BACKUP_DIR)
    os.makedirs(CURRENT_BACKUP_PATH)
    
    # Backup arquivos sensíveis
    for f in ["src/components/RouteList.jsx", "src/components/MapView.jsx"]:
        if os.path.exists(f):
            dest = os.path.join(CURRENT_BACKUP_PATH, os.path.basename(f))
            shutil.copy2(f, dest)

    print("--- Aplicando atualizações do Ajustesfinos.txt ---")
    for path, content in FILES_TO_WRITE.items():
        dir_name = os.path.dirname(path)
        if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    print("--- Git Push Automático ---")
    run_command("git add .")
    run_command(f'git commit -m "Update v3: Ajustes Finos aplicados - {TIMESTAMP}"')
    run_command("git push")

    print("--- Auto-Destruição ---")
    os.remove(__file__)
    print("Concluído com sucesso.")

if __name__ == "__main__":
    main()

