import React from 'react';
import { Check, ChevronUp, ChevronDown } from 'lucide-react';

export default function RouteList({ 
    groupedStops, 
    nextGroup, 
    activeRoute, 
    searchQuery, 
    expandedGroups, 
    toggleGroup, 
    setStatus 
}) {
    // Helper seguro para strings
    const safeStr = (val) => {
        if (val === null || val === undefined) return '';
        return String(val).trim();
    };

    // Filtro de busca
    const filteredGroups = !searchQuery ? groupedStops : groupedStops.filter(g => 
        safeStr(g.mainName).toLowerCase().includes(searchQuery.toLowerCase()) || 
        safeStr(g.mainAddress).toLowerCase().includes(searchQuery.toLowerCase())
    );

    return (
        <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3">
            {/* CARD DE DESTAQUE (PRÓXIMA PARADA) */}
            {!searchQuery && nextGroup && activeRoute.optimized && (
                <div className="modern-card p-6 border-l-4 border-slate-900 bg-white relative mb-6 shadow-md">
                    <div className="absolute top-0 right-0 bg-slate-900 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">PRÓXIMO</div>
                    <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">Parada: {safeStr(nextGroup.mainName)}</h3>
                    <p className="text-sm text-slate-500 mb-4">{nextGroup.items.length} pacotes a serem entregues nessa parada</p>
                    <div className="space-y-3 border-t border-slate-100 pt-3">
                        {nextGroup.items.map((item, idx) => {
                            if (item.status !== 'pending') return null;
                            return (
                                <div key={item.id} className="flex flex-col bg-slate-50 p-3 rounded-lg border border-slate-100">
                                    <div className="mb-3">
                                        <span className="text-xs font-bold text-blue-600 block mb-1">PACOTE #{idx + 1}</span>
                                        <span className="text-sm font-bold text-slate-800 block leading-tight">{safeStr(item.address)}</span>
                                    </div>
                                    <div className="flex gap-2 w-full">
                                        <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 btn-action-lg btn-outline-red rounded-xl">Não Entregue</button>
                                        <button onClick={() => setStatus(item.id, 'success')} className="flex-1 btn-action-lg btn-gradient-green rounded-xl text-white shadow-md">ENTREGUE</button>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}

            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">Lista Completa</h4>
            
            {filteredGroups.map((group, idx) => {
                // Não mostra o grupo se ele já estiver no card de destaque
                if (!searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) return null;
                
                const isExpanded = expandedGroups[group.id];
                const hasMulti = group.items.length > 1;
                const statusClass = `border-l-status-${group.status}`;
                
                return (
                    <div key={group.id} className={`modern-card overflow-hidden ${statusClass} ${group.status !== 'pending' && !searchQuery ? 'opacity-60 grayscale' : ''}`}>
                        <div onClick={() => toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                            <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                {group.status === 'success' ? <Check size={14}/> : (idx + 1)}
                            </div>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2"><h4 className="font-bold text-slate-800 text-sm truncate">Parada: {safeStr(group.mainName)}</h4></div>
                                <p className="text-xs text-slate-400 truncate">{group.items.length} pacotes a serem entregues nessa parada</p>
                            </div>
                            {hasMulti || isExpanded ? (isExpanded ? <ChevronUp size={18}/> : <ChevronDown size={18}/>) : (
                                group.items[0].status === 'pending' && 
                                <button onClick={(e) => {e.stopPropagation(); setStatus(group.items[0].id, 'success')}} className="p-2 bg-slate-50 text-slate-400 rounded-full"><Check size={18}/></button>
                            )}
                        </div>
                        {(isExpanded || (hasMulti && isExpanded)) && (
                            <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-3">
                                {group.items.map((item) => (
                                    <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                        <div className="mb-2">
                                            <span className="text-[10px] font-bold text-blue-500 block">ENDEREÇO</span>
                                            <span className="text-sm font-bold text-slate-700 block">{safeStr(item.address)}</span>
                                        </div>
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-2 w-full">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 btn-outline-red rounded font-bold text-xs">NÃO ENTREGUE</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 btn-gradient-green rounded font-bold text-xs text-white shadow-sm">ENTREGUE</button>
                                            </div>
                                        ) : (
                                            <span className="text-xs font-bold">{item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )
            })}
            <div className="h-10"></div>
        </div>
    );
}
