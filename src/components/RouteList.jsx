import React, { useState } from 'react';
import { Check, ChevronUp, ChevronDown, Layers, Edit3, Save } from 'lucide-react';

export default function RouteList({ 
    groupedStops, 
    nextGroup, 
    activeRoute, 
    searchQuery, 
    expandedGroups, 
    toggleGroup, 
    setStatus,
    onReorder // Nova prop para reordenar
}) {
    const [isEditing, setIsEditing] = useState(false);
    const [editValues, setEditValues] = useState({});

    const safeStr = (val) => val ? String(val).trim() : '';

    const setAllStatus = (items, status) => {
        items.forEach(item => {
            if (item.status === 'pending') setStatus(item.id, status);
        });
    };

    // Filtra visualização
    const filteredGroups = !searchQuery ? groupedStops : groupedStops.filter(g => 
        safeStr(g.mainName).toLowerCase().includes(searchQuery.toLowerCase()) || 
        safeStr(g.mainAddress).toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleInputChange = (groupId, value) => {
        setEditValues(prev => ({...prev, [groupId]: value}));
    };

    const handleInputBlur = (group, oldIndex) => {
        const newIndex = parseInt(editValues[group.id]);
        if (!isNaN(newIndex) && newIndex > 0 && newIndex <= groupedStops.length) {
            // Ajusta para índice 0-based
            onReorder(oldIndex, newIndex - 1); 
        }
        setEditValues(prev => ({...prev, [group.id]: ''}));
    };

    return (
        <div className="flex-1 overflow-y-auto px-5 pt-4 pb-safe space-y-3 relative">
            
            {/* BOTÃO FLUTUANTE DE EDIÇÃO */}
            {!searchQuery && (
                <div className="flex justify-end mb-2">
                    <button 
                        onClick={() => setIsEditing(!isEditing)} 
                        className={`text-xs font-bold px-3 py-1.5 rounded-full flex items-center gap-2 transition
                        ${isEditing ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-600'}`}
                    >
                        {isEditing ? <Save size={14}/> : <Edit3 size={14}/>}
                        {isEditing ? 'SALVAR ORDEM' : 'EDITAR SEQUÊNCIA'}
                    </button>
                </div>
            )}

            {/* DESTAQUE (SÓ APARECE SE NÃO ESTIVER EDITANDO) */}
            {!isEditing && !searchQuery && nextGroup && activeRoute.optimized && (
                <div className="modern-card p-6 border-l-8 border-blue-600 bg-white relative mb-6 shadow-lg">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl">ALVO ATUAL</div>
                    <h3 className="text-xl font-bold text-slate-900 leading-tight mb-1">{nextGroup.mainName}</h3>
                    <p className="text-sm text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                    
                    {nextGroup.items.filter(i => i.status === 'pending').length > 1 && (
                        <button 
                            onClick={() => setAllStatus(nextGroup.items, 'success')}
                            className="w-full mb-4 py-2 bg-green-100 text-green-700 rounded-lg text-xs font-bold flex items-center justify-center gap-2 active:scale-95 transition"
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

            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest pl-1">
                {isEditing ? 'Reordenar Paradas' : 'Sequência da Rota'}
            </h4>
            
            {filteredGroups.map((group, idx) => (
                (!isEditing && !searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) ? null : (
                    <div key={group.id} className={`modern-card border-l-4 ${group.status === 'success' ? 'border-green-500 opacity-60' : 'border-slate-200'}`}>
                        <div onClick={() => !isEditing && toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer">
                            
                            {/* MODO EDIÇÃO: INPUT AO INVÉS DE BOLINHA */}
                            {isEditing ? (
                                <input 
                                    type="number" 
                                    className="w-12 h-10 bg-slate-100 rounded-lg text-center font-bold text-lg outline-none border-2 focus:border-blue-500"
                                    placeholder={idx + 1}
                                    value={editValues[group.id] !== undefined ? editValues[group.id] : ''}
                                    onChange={(e) => handleInputChange(group.id, e.target.value)}
                                    onBlur={() => handleInputBlur(group, idx)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleInputBlur(group, idx)}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            ) : (
                                <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center font-bold text-xs shrink-0">
                                    {group.status === 'success' ? <Check size={14} className="text-green-600"/> : (idx + 1)}
                                </div>
                            )}

                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">{group.mainName}</h4>
                                <p className="text-xs text-slate-400 truncate">{group.items.length} pacote(s)</p>
                            </div>
                            
                            {!isEditing && group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp/> : <ChevronDown/>) : null}
                        </div>
                    </div>
                )
            ))}
            <div className="h-10"></div>
        </div>
    );
}
