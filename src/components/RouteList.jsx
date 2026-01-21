import React, { useState } from 'react';
import { Check, ChevronUp, ChevronDown, Layers, Edit3, Save, Package } from 'lucide-react';

export default function RouteList(props) {
    const { 
        groupedStops = [], 
        nextGroup = null, 
        activeRoute = {}, 
        searchQuery = '', 
        expandedGroups = {}, 
        toggleGroup, 
        setStatus,
        onReorder 
    } = props;

    const [isEditing, setIsEditing] = useState(false);
    const [editValues, setEditValues] = useState({});

    const safeStr = (val) => val ? String(val).trim() : '';

    const setAllStatus = (items, status) => {
        items.forEach(item => {
            if (item.status === 'pending') setStatus(item.id, status);
        });
    };

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
            onReorder(oldIndex, newIndex - 1); 
        }
        setEditValues(prev => ({...prev, [group.id]: ''}));
    };

    return (
        <div className="flex-1 overflow-y-auto px-4 pt-4 pb-safe space-y-3 relative bg-slate-50">
            
            {!searchQuery && (
                <div className="flex justify-end mb-2">
                    <button 
                        onClick={() => setIsEditing(!isEditing)} 
                        className={`text-[10px] font-bold px-3 py-1.5 rounded-full flex items-center gap-2 transition uppercase tracking-wider
                        ${isEditing ? 'bg-slate-900 text-white shadow-lg' : 'bg-white text-slate-500 border border-slate-200'}`}
                    >
                        {isEditing ? <Save size={12}/> : <Edit3 size={12}/>}
                        {isEditing ? 'Salvar Ordem' : 'Editar Sequência'}
                    </button>
                </div>
            )}

            {!isEditing && !searchQuery && nextGroup && activeRoute.optimized && (
                <div className="bg-white rounded-2xl p-5 border-l-4 border-blue-600 shadow-md relative overflow-hidden mb-6">
                    <div className="absolute top-0 right-0 bg-blue-600 text-white px-3 py-1 text-[10px] font-bold rounded-bl-xl uppercase">Próxima Parada</div>
                    
                    <h3 className="text-lg font-bold text-slate-900 leading-tight mb-1 pr-20">Parada: {safeStr(nextGroup.mainName)}</h3>
                    <p className="text-xs text-slate-500 mb-4">{nextGroup.mainAddress}</p>
                    
                    {nextGroup.items.filter(i => i.status === 'pending').length > 1 && (
                        <button 
                            onClick={() => setAllStatus(nextGroup.items, 'success')}
                            className="w-full mb-4 py-3 bg-blue-50 text-blue-700 rounded-xl text-xs font-bold flex items-center justify-center gap-2 border border-blue-100 active:scale-95 transition"
                        >
                            <Layers size={16}/> ENTREGAR TODOS ({nextGroup.items.filter(i => i.status === 'pending').length})
                        </button>
                    )}

                    <div className="space-y-3 border-t border-slate-100 pt-3">
                        {nextGroup.items.map((item, idx) => (
                            item.status === 'pending' && (
                                <div key={item.id} className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                                    <div className="flex items-center gap-2 mb-2">
                                        <Package size={14} className="text-blue-400"/>
                                        <span className="text-xs font-bold text-slate-700">PACOTE {idx + 1}</span>
                                    </div>
                                    <p className="text-xs font-medium text-slate-600 mb-3 ml-6">{item.address}</p>
                                    <div className="flex gap-2">
                                        <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-3 bg-white border border-red-100 text-red-500 rounded-lg text-[10px] font-bold uppercase shadow-sm">Falha</button>
                                        <button onClick={() => setStatus(item.id, 'success')} className="flex-[2] py-3 bg-green-500 text-white rounded-lg text-[10px] font-bold uppercase shadow-md active:scale-95 transition">Entregue</button>
                                    </div>
                                </div>
                            )
                        ))}
                    </div>
                </div>
            )}

            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-1 mb-2">
                {isEditing ? 'Digite a nova posição' : 'Lista de Entregas'}
            </h4>
            
            {filteredGroups.map((group, idx) => (
                (!isEditing && !searchQuery && nextGroup && group.id === nextGroup.id && activeRoute.optimized) ? null : (
                    <div key={group.id} className={`bg-white rounded-xl shadow-sm border-l-4 overflow-hidden ${group.status === 'success' ? 'border-green-400 opacity-60' : 'border-slate-300'}`}>
                        <div onClick={() => !isEditing && toggleGroup && toggleGroup(group.id)} className="p-4 flex items-center gap-4 cursor-pointer active:bg-slate-50 transition">
                            
                            {isEditing ? (
                                <input 
                                    type="number" 
                                    className="w-10 h-10 bg-slate-100 rounded-lg text-center font-bold text-base outline-none border-2 border-transparent focus:border-blue-500 focus:bg-white transition-all"
                                    placeholder={idx + 1}
                                    value={editValues[group.id] !== undefined ? editValues[group.id] : ''}
                                    onChange={(e) => handleInputChange(group.id, e.target.value)}
                                    onBlur={() => handleInputBlur(group, idx)}
                                    onKeyDown={(e) => e.key === 'Enter' && handleInputBlur(group, idx)}
                                    onClick={(e) => e.stopPropagation()}
                                />
                            ) : (
                                <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 ${group.status === 'success' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                                    {group.status === 'success' ? <Check size={14}/> : (idx + 1)}
                                </div>
                            )}

                            <div className="flex-1 min-w-0">
                                <h4 className="font-bold text-slate-800 text-sm truncate">Parada: {safeStr(group.mainName)}</h4>
                                <p className="text-[11px] text-slate-400 truncate mt-0.5">{group.items.length} pacote(s) • {safeStr(group.mainAddress)}</p>
                            </div>
                            
                            {!isEditing && group.items.length > 1 ? (expandedGroups[group.id] ? <ChevronUp size={16} className="text-slate-300"/> : <ChevronDown size={16} className="text-slate-300"/>) : null}
                        </div>
                        
                        {(expandedGroups[group.id] || (isEditing === false && group.items.length > 1 && expandedGroups[group.id])) && (
                            <div className="bg-slate-50 border-t border-slate-100 px-4 py-2 space-y-2">
                                {group.items.map((item) => (
                                    <div key={item.id} className="flex flex-col py-2 border-b border-slate-200 last:border-0">
                                        <div className="mb-2">
                                            <span className="text-[10px] font-bold text-blue-500 block uppercase mb-0.5">Endereço</span>
                                            <span className="text-xs font-medium text-slate-700 block leading-tight">{item.address}</span>
                                        </div>
                                        {item.status === 'pending' ? (
                                            <div className="flex gap-2 w-full">
                                                <button onClick={() => setStatus(item.id, 'failed')} className="flex-1 py-2 bg-white border border-red-200 text-red-500 rounded-lg font-bold text-[10px] uppercase">Falha</button>
                                                <button onClick={() => setStatus(item.id, 'success')} className="flex-1 py-2 bg-green-500 text-white rounded-lg font-bold text-[10px] uppercase shadow-sm">Entregue</button>
                                            </div>
                                        ) : (
                                            <span className={`text-[10px] font-bold px-2 py-1 rounded w-fit ${item.status==='success'?'bg-green-100 text-green-700':'bg-red-100 text-red-700'}`}>
                                                {item.status === 'success' ? 'ENTREGUE' : 'NÃO ENTREGUE'}
                                            </span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )
            ))}
            <div className="h-12"></div>
        </div>
    );
}
