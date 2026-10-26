/* VietGeo Nova — original, dependency-light browser client. All user strings are rendered as text. */
'use strict';
const $ = (id) => document.getElementById(id);
const cfg = { version:'2026.10', all:[102.0,8.4,110.3,23.6] };
const state = { map:null, lib:null, places:[], provinces:[], category:'', province:'', query:'', nearby:null,
  favorites:new Set(JSON.parse(localStorage.getItem('vietgeo.favorites')||'[]')), onlyFavorites:false,
  admin:false, current:null, addClick:false, style:'liberty', abort:null, revision:null, scanBusy:false };
const catSymbols = {'Ẩm thực':'☕','Mua sắm':'▣','Y tế':'✚','Giáo dục':'▤','Lưu trú':'⌂','Du lịch':'◇','Giao thông':'➜','Dịch vụ':'●','Công cộng':'◎','Thể thao':'⚑','Khác':'•'};
let refreshTimer, toastTimer;

function toast(message, duration=3300) { const e=$('toast'); e.textContent=message; e.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>e.classList.remove('show'),duration); }
function text(parent, tag, value, className='') { const el=document.createElement(tag);el.textContent=String(value??''); if(className)el.className=className;parent.append(el);return el; }
function safeNumber(value,digits=5) {return Number.isFinite(Number(value))?Number(value).toFixed(digits):'–';}
function apiPath(path,params={}) {const q=new URLSearchParams();Object.entries(params).forEach(([k,v])=>{if(v!==''&&v!==null&&v!==undefined)q.set(k,String(v));});return path+(q.size?'?'+q:'');}
async function request(path,options={}) {const { token, ...rest }=options;
  const headers={...(options.body?{'Content-Type':'application/json'}:{}),...(rest.headers||{})};
  const secret=$('api-token')?.value;
  if(secret)headers.Authorization='Bearer '+secret;
  const res=await fetch(path,{...rest,headers});let data;const kind=res.headers.get('content-type')||'';
  try{data=kind.includes('json')?await res.json():await res.text();}catch{data={error:'Không đọc được phản hồi'};}
  if(!res.ok)throw new Error(data.error||`HTTP ${res.status}`);return data;
}
function saveFavorites(){localStorage.setItem('vietgeo.favorites',JSON.stringify([...state.favorites]));}
function categorySymbol(category){return catSymbols[category]||'●';}
function categoryOptions(categories){const select=$('category');const selected=select.value;select.replaceChildren(new Option('Mọi danh mục',''));
  (categories||[]).forEach(x=>select.add(new Option(`${x.category} (${x.count})`,x.category)));
  select.value=[...select.options].some(o=>o.value===selected)?selected:'';
}
function makeFeature(p){return {type:'Feature',id:p.id,properties:{id:p.id,category:p.category,name:p.name},geometry:{type:'Point',coordinates:[p.lon,p.lat]}};}
function updateSource(){const s=state.map?.getSource('poi');if(s)s.setData({type:'FeatureCollection',features:state.places.map(makeFeature)});}
function drawResults(){const container=$('results');container.replaceChildren();let items=state.places;
  if(state.onlyFavorites)items=items.filter(p=>state.favorites.has(p.id));
  $('visible-count').textContent=items.length.toLocaleString('vi-VN');
  $('result-note').textContent=items.length>=400?'Hiển thị tối đa 400 điểm':'Trong vùng / kết quả tìm kiếm';
  if(!items.length){const e=text(container,'div',state.onlyFavorites?'Chưa có địa điểm được lưu trong vùng này.':
    'Chưa có điểm dữ liệu ở khu vực này. Thử tìm kiếm toàn quốc, hoặc chọn “Nạp OSM vùng”.','empty');return;}
  for(const p of items) {
    const card=document.createElement('article');card.className='result-card'+(state.current?.id===p.id?' selected':'');card.tabIndex=0;
    card.setAttribute('role','button');card.setAttribute('aria-label','Mở '+p.name);
    text(card,'div',categorySymbol(p.category),'result-icon');
    const body=text(card,'div','','result-main');text(body,'div',p.name,'result-name');
    text(body,'div',p.address||p.province||'Chưa có địa chỉ đầy đủ','result-sub');
    const chips=text(body,'div','','result-chips');text(chips,'span',p.category||'Khác','small-chip');
    if(p.distance_m!==undefined)text(chips,'span',(p.distance_m/1000).toFixed(1)+' km','small-chip muted');
    if(p.source==='osm')text(chips,'span','OSM','small-chip muted');
    const star=text(card,'button',state.favorites.has(p.id)?'★':'☆','fav'+(state.favorites.has(p.id)?' on':''));star.title='Lưu / bỏ lưu';
    star.addEventListener('click',ev=>{ev.stopPropagation();if(state.favorites.has(p.id))state.favorites.delete(p.id);else state.favorites.add(p.id);saveFavorites();drawResults();});
    card.addEventListener('click',()=>openPlace(p,true));card.addEventListener('keydown',e=>{if(e.key==='Enter')openPlace(p,true);});container.append(card);
  }
}
function buildPopup(p){const root=document.createElement('div');text(root,'div',p.name,'popup-name');
  text(root,'div',(p.address||p.province||'Chưa có địa chỉ')+' · '+(p.category||'Khác'),'popup-address');
  if(p.source==='osm')text(root,'div','Nguồn: OpenStreetMap (ODbL)','popup-address');
  const bar=text(root,'div','','popup-actions');
  const directions=text(bar,'a','Chỉ đường');directions.href=`https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route=%3B${p.lat}%2C${p.lon}`;
  directions.target='_blank';directions.rel='noopener noreferrer';
  const copy=text(bar,'button','Sao chép GPS');copy.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(`${p.lat}, ${p.lon}`);toast('Đã sao chép tọa độ');}catch{toast(`${p.lat}, ${p.lon}`);}});
  if(p.source==='user') {const edit=text(bar,'button','Chỉnh sửa');edit.addEventListener('click',()=>{state.map._popup?.remove();openEditor(p);});}
  return root;
}
function openPlace(p,fly=false){if(!state.map)return;state.current=p;drawResults();
  if(fly)state.map.flyTo({center:[p.lon,p.lat],zoom:Math.max(state.map.getZoom(),13),duration:700});
  const popup=new state.lib.Popup({offset:16,maxWidth:'330px'}).setLngLat([p.lon,p.lat]).setDOMContent(buildPopup(p)).addTo(state.map);
  state.map._popup=popup;
}
function searchArgs(){const args={limit:400};if(state.query.trim())args.search=state.query.trim();
  if(state.province)args.province=state.province;if(state.category)args.category=state.category;
  if(state.nearby){args.near=state.nearby.join(',');args.radius_m=12000;}
  else if(!state.query.trim()&&!state.province){const b=state.map.getBounds();args.bbox=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].map(x=>x.toFixed(5)).join(',');}
  return args;
}
async function refresh(){if(!state.map)return;
  state.abort?.abort();state.abort=new AbortController();const signal=state.abort.signal;
  try{const data=await request(apiPath('/api/places',searchArgs()),{signal});state.places=data.items||[];updateSource();drawResults();}
  catch(e){if(e.name!=='AbortError')toast('Không thể tải dữ liệu: '+e.message);}
}
function scheduleRefresh(){clearTimeout(refreshTimer);refreshTimer=setTimeout(refresh,280);}
async function updateStats(){try{const s=await request('/api/stats');$('total-count').textContent=(s.places||0).toLocaleString('vi-VN');
  $('dataset-status').textContent=s.places?'Dữ liệu: '+Object.entries(Object.fromEntries((s.by_source||[]).map(i=>[i.source,i.count]))).map(([k,v])=>`${k} ${v.toLocaleString('vi-VN')}`).join(' · '):'Chưa có POI: nhấn Nạp OSM vùng hoặc nhập PBF';
  state.revision=s.revision;categoryOptions(s.categories);}
 catch(e){console.warn(e);}}
async function pollRevision(){try{const r=await request('/api/revision');if(state.revision&&r.revision!==state.revision){state.revision=r.revision;await Promise.all([updateStats(),refresh()]);}}catch{}}
async function showAdmin(){if(!state.map?.getSource('admin'))return;
  const feature=(x,ward=false)=>({type:'Feature',geometry:{type:'Point',coordinates:[+x.lon,+x.lat]},properties:{name:x.name,code:x.code,kind:ward?'Xã/phường':'Tỉnh/thành',province_code:x.province_code||x.code}});
  let units=state.provinces.map(x=>feature(x));
  if(state.admin&&state.province){try{const data=await request(apiPath('/api/admin/wards',{province:state.provinces.find(p=>p.name===state.province)?.code||''}));
    if(data.installed)units=data.items.filter(x=>Number.isFinite(+x.lat)&&Number.isFinite(+x.lon)).map(x=>feature(x,true));
    else toast('Chưa có 3.321 xã/phường. Chạy tools/sync_admin.py để tải.');}catch(e){toast(e.message);}}
  state.map.getSource('admin').setData({type:'FeatureCollection',features:units});
  for(const layer of ['admin-dots','admin-labels'])state.map.setLayoutProperty(layer,'visibility',state.admin?'visible':'none');
}
function initLayers(){const map=state.map;
  map.addSource('poi',{type:'geojson',data:{type:'FeatureCollection',features:[]},cluster:true,clusterMaxZoom:13,clusterRadius:52});
  map.addLayer({id:'clusters',type:'circle',source:'poi',filter:['has','point_count'],paint:{'circle-color':['step',['get','point_count'],'#06765e',40,'#166c98',150,'#27386e'],'circle-radius':['step',['get','point_count'],20,40,28,150,36],'circle-stroke-width':3,'circle-stroke-color':'#ffffff'}});
  map.addLayer({id:'cluster-label',type:'symbol',source:'poi',filter:['has','point_count'],layout:{'text-field':['get','point_count_abbreviated'],'text-font':['Noto Sans Regular'],'text-size':13},paint:{'text-color':'#fff'}});
  map.addLayer({id:'unclustered',type:'circle',source:'poi',filter:['!',['has','point_count']],paint:{'circle-color':'#0b9e77','circle-radius':8,'circle-stroke-color':'#fff','circle-stroke-width':2.5}});
  map.addSource('admin',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'admin-dots',type:'circle',source:'admin',layout:{visibility:'none'},paint:{'circle-color':'#faad46','circle-radius':5,'circle-stroke-color':'#fff','circle-stroke-width':1.5}});
  map.addLayer({id:'admin-labels',type:'symbol',source:'admin',layout:{visibility:'none','text-field':['get','name'],'text-size':12,'text-offset':[0,1.25],'text-anchor':'top','text-optional':true},paint:{'text-color':'#7c4b07','text-halo-color':'#ffffff','text-halo-width':1.8}});
  map.on('click','clusters',async e=>{const f=map.queryRenderedFeatures(e.point,{layers:['clusters']})[0];if(!f)return;
    try{const z=await map.getSource('poi').getClusterExpansionZoom(f.properties.cluster_id);map.easeTo({center:f.geometry.coordinates,zoom:z});}catch{}});
  map.on('click','unclustered',e=>{const f=e.features?.[0];if(!f)return;const p=state.places.find(x=>x.id===+f.properties.id);if(p)openPlace(p);});
  map.on('click','admin-dots',e=>{if(!e.features?.length)return;const p=e.features[0];const pop=document.createElement('div');text(pop,'div',p.properties.name,'popup-name');text(pop,'div',p.properties.kind+' · Mã '+p.properties.code,'popup-address');
    new state.lib.Popup().setLngLat(p.geometry.coordinates).setDOMContent(pop).addTo(map);});
  for(const layer of ['clusters','unclustered','admin-dots']){map.on('mouseenter',layer,()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave',layer,()=>map.getCanvas().style.cursor='');}
  updateSource();showAdmin();
}
function openEditor(p=null){$('modal').hidden=false;$('modal-title').textContent=p?'Chỉnh sửa địa điểm':'Thêm địa điểm mới';$('delete-place').hidden=!p;
  $('place-id').value=p?.id||'';$('place-name').value=p?.name||'';$('place-category').value=p?.category||'Dịch vụ';
  $('place-address').value=p?.address||'';$('place-province').value=p?.province||'';
  $('place-lat').value=p?.lat??'';$('place-lon').value=p?.lon??'';$('place-source-url').value=p?.source_url||'';
  setTimeout(()=>$('place-name').focus(),30);
}
function closeEditor(){$('modal').hidden=true;state.addClick=false;}
function selectedPayload(){return {name:$('place-name').value.trim(),category:$('place-category').value.trim()||'Dịch vụ',address:$('place-address').value.trim(),
 province:$('place-province').value,lat:Number($('place-lat').value),lon:Number($('place-lon').value),source_url:$('place-source-url').value.trim()};}
async function savePlace(ev){ev.preventDefault();const p=selectedPayload();if(!p.name||!$('place-lat').value||!$('place-lon').value){toast('Cần tên và tọa độ');return;}
  const id=$('place-id').value;try{await request(id?'/api/places/'+id:'/api/places',{method:id?'PUT':'POST',body:JSON.stringify(p)});
  closeEditor();toast(id?'Đã cập nhật địa điểm':'Đã lưu địa điểm');await Promise.all([refresh(),updateStats()]);}
  catch(e){toast('Không lưu được: '+e.message,6000);}}
async function deletePlace(){const id=$('place-id').value;if(!id||!confirm('Xóa địa điểm tự tạo này?'))return;
  try{await request('/api/places/'+id,{method:'DELETE'});closeEditor();state.map._popup?.remove();toast('Đã xóa địa điểm');await Promise.all([refresh(),updateStats()]);}
  catch(e){toast(e.message);}}
function parseCSV(raw){const lines=[];let row=[],field='',quoted=false;
  for(let i=0;i<raw.length;i++){const c=raw[i];if(quoted){if(c==='"'&&raw[i+1]==='"'){field+='"';i++;}else if(c==='"')quoted=false;else field+=c;}
  else if(c==='"')quoted=true;else if(c===','){row.push(field);field='';}else if(c==='\n'){row.push(field.replace(/\r$/,''));lines.push(row);row=[];field='';}else field+=c;}
  if(quoted)throw Error('CSV có dấu nháy kép chưa đóng');if(field||row.length){row.push(field);lines.push(row);}
  if(lines.length<2)throw Error('CSV trống');const header=lines.shift().map(x=>x.trim().replace(/^\ufeff/,''));
  return lines.filter(x=>x.some(y=>y.trim())).map(row=>Object.fromEntries(header.map((name,i)=>[name,row[i]||''])));
}
async function importFile(file){if(!file)return;if(file.size>15*1024*1024){toast('Tệp quá 15 MB. Hãy dùng tools/import_osm.py cho dữ liệu lớn.');return;}
  try{const raw=await file.text();const obj=file.name.toLowerCase().endsWith('.csv')?parseCSV(raw):JSON.parse(raw);
    const rows=Array.isArray(obj)?obj:(obj?.type==='FeatureCollection'?obj.features.map(f=>({...f.properties,lon:f.geometry?.coordinates?.[0],lat:f.geometry?.coordinates?.[1]})):null);
    if(!rows||rows.length>10000)throw Error('Cần CSV, JSON array hoặc GeoJSON Point (tối đa 10.000 bản ghi)');
    if(!confirm(`Nhập ${rows.length} địa điểm vào SQLite trên máy?`))return;
    let done=0;for(let i=0;i<rows.length;i+=400){const batch=rows.slice(i,i+400);await request('/api/import',{method:'POST',body:JSON.stringify(batch)});done+=batch.length;toast('Đang nhập '+done+' / '+rows.length,1000);}
    toast('Đã nhập '+done+' bản ghi.');await Promise.all([refresh(),updateStats()]);}
  catch(e){toast('Lỗi nhập: '+e.message,6500);}finally{$('file-input').value='';}
}
async function scanOSMArea(){if(state.scanBusy)return;const b=state.map.getBounds();const box=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()];
  if((box[2]-box[0])*(box[3]-box[1])>.25){toast('Hãy phóng to đến một quận / khu vực nhỏ trước khi nạp OSM.',5000);return;}
  if(!confirm('Tải POI OpenStreetMap từ Overpass cho vùng đang xem? Chỉ những điểm có tên sẽ được lưu.'))return;
  state.scanBusy=true;$('load-osm-area').disabled=true;$('load-osm-area').textContent='Đang nạp…';
  try{const r=await request('/api/osm/area',{method:'POST',body:JSON.stringify({bbox:box})});toast(`OpenStreetMap: ${r.imported} điểm đã lưu / ${r.fetched} đối tượng`);
    await Promise.all([refresh(),updateStats()]);}catch(e){toast('Không nạp được OSM: '+e.message,6500);}finally{state.scanBusy=false;$('load-osm-area').disabled=false;$('load-osm-area').textContent='Nạp OSM vùng';}
}
function setupControls(){
  $('search').addEventListener('input',e=>{state.query=e.target.value;scheduleRefresh();});
  $('clear-search').onclick=()=>{$('search').value='';state.query='';refresh();};
  $('province').addEventListener('change',e=>{state.province=e.target.value;showAdmin();refresh();
    const p=state.provinces.find(x=>x.name===state.province);if(p)state.map.flyTo({center:[p.lon,p.lat],zoom:8});});
  $('category').onchange=e=>{state.category=e.target.value;refresh();};
  $('nearby').onclick=()=>{if(state.nearby){state.nearby=null;$('nearby').classList.remove('active');refresh();return;}
    if(!navigator.geolocation){toast('Trình duyệt không hỗ trợ định vị');return;}
    navigator.geolocation.getCurrentPosition(pos=>{state.nearby=[pos.coords.latitude,pos.coords.longitude];$('nearby').classList.add('active');state.map.flyTo({center:[state.nearby[1],state.nearby[0]],zoom:13});refresh();},
      e=>toast('Không thể lấy vị trí: '+e.message),{enableHighAccuracy:true,timeout:14000});};
  $('admin-toggle').onclick=e=>{state.admin=!state.admin;e.currentTarget.classList.toggle('active',state.admin);showAdmin();};
  $('bookmark-toggle').onclick=e=>{state.onlyFavorites=!state.onlyFavorites;e.currentTarget.classList.toggle('active',state.onlyFavorites);drawResults();};
  $('reset-view').onclick=()=>{state.map.fitBounds([[102,8.1],[110.8,23.9]],{padding:60,duration:1200});};
  $('geo-locate').onclick=()=>$('nearby').click();
  $('add-location').onclick=()=>{state.addClick=true;toast('Bấm vị trí trên bản đồ để thêm địa điểm.',4300);};
  $('import-file').onclick=()=>$('file-input').click();$('file-input').onchange=e=>importFile(e.target.files?.[0]);
  $('export-data').onclick=()=>{const a=document.createElement('a');a.href='/api/export.geojson?limit=20000';a.download='vietgeo-next.geojson';a.click();};
  $('load-osm-area').onclick=scanOSMArea;
  $('place-form').onsubmit=savePlace;$('delete-place').onclick=deletePlace;
  $('close-modal').onclick=closeEditor;$('cancel-modal').onclick=closeEditor;
  $('modal').onclick=e=>{if(e.target===$('modal'))closeEditor();};
  document.addEventListener('keydown',e=>{if(e.key==='Escape')closeEditor();if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();$('search').focus();}});
  $('mobile-menu').onclick=()=>$('sidebar').classList.toggle('open');
  $('base-style').onchange=e=>{state.style=e.target.value;state.map.setStyle('https://tiles.openfreemap.org/styles/'+state.style);};
  $('copy-coordinates').onclick=async()=>{const c=state.map.getCenter(),v=`${c.lat.toFixed(6)}, ${c.lng.toFixed(6)}`;
    try{await navigator.clipboard.writeText(v);toast('Đã sao chép '+v);}catch{toast(v);}};
  $('pitch').onclick=()=>{const p=state.map.getPitch();state.map.easeTo({pitch:p>20?0:55,duration:800});};
}
async function loadAdministrative(){try{const r=await request('/api/provinces');state.provinces=r.items||[];
  for(const p of state.provinces){$('province').add(new Option(p.name,p.name));$('place-province').add(new Option(p.name,p.name));}}
  catch(e){toast('Lỗi dữ liệu hành chính: '+e.message);}}
async function boot(){setupControls();await loadAdministrative();await updateStats();
  try{state.lib=await import('https://unpkg.com/maplibre-gl@6.15.0/dist/maplibre-gl.mjs');
    const map=new state.lib.Map({container:'map',style:'https://tiles.openfreemap.org/styles/liberty',center:[106.1,16.2],zoom:5,
      pitch:0,bearing:0,maxPitch:70,minZoom:3,hash:true,attributionControl:true});state.map=map;
    map.addControl(new state.lib.NavigationControl({visualizePitch:true}),'bottom-right');
    map.addControl(new state.lib.ScaleControl({maxWidth:150,unit:'metric'}),'bottom-left');
    map.on('style.load',()=>{initLayers();refresh();});
    map.on('moveend',scheduleRefresh);
    map.on('mousemove',e=>{$('copy-coordinates').textContent=`${safeNumber(e.lngLat.lat,4)}° N · ${safeNumber(e.lngLat.lng,4)}° E`;});
    map.on('click',e=>{if(!state.addClick)return;const features=map.queryRenderedFeatures(e.point,{layers:['clusters','unclustered']});if(features.length)return;
      state.addClick=false;openEditor();$('place-lat').value=e.lngLat.lat.toFixed(7);$('place-lon').value=e.lngLat.lng.toFixed(7);});
    map.on('error',e=>console.warn('Tile/map provider:',e?.error?.message||e));
    setInterval(pollRevision,12000);
  }catch(e){console.error(e);$('map-error').hidden=false;$('map-error').textContent='Không khởi chạy được MapLibre: '+e.message+'. Kiểm tra Internet hoặc tường lửa.';}
}
boot();
