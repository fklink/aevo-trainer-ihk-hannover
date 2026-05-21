let data, order=[], idx=0, mode='practice', answers={}, practiceResults={}, examSubmitted=false, examError='';
const letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
const EDITOR_PASSWORD='aevo-editor';
loadQuestions();

function start(j){data=j; resetProgress();}
function loadQuestions(){
  if(window.QUESTIONS_DATA){start(window.QUESTIONS_DATA); return;}
  fetch('questions.json').then(r=>r.json()).then(start).catch(()=>{
    document.getElementById('app').innerHTML='<strong>Fragen konnten nicht geladen werden.</strong><p>Die Datei questions.js fehlt. Lege sie neben index.html ab oder starte einen lokalen Webserver.</p>';
  });
}
function q(){return data.questions[order[idx]]}
function key(){return String(order[idx])}
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function questionText(qu){return qu.question||qu.text||qu.prompt||''}
function hasTextQuestion(qu){return Boolean(questionText(qu)||Array.isArray(qu.options))}
function hasSolution(qu){return Array.isArray(qu.correct)&&qu.correct.length>0&&qu.correct.every(v=>v!==null&&v!==undefined)&&qu.solutionAvailable!==false}

function importWarnings(qu){
  const warnings=Array.isArray(qu.importWarnings)?[...qu.importWarnings]:[];
  if(qu.type==='choice'&&qu.expectedCorrectCount&&hasSolution(qu)){
    const actual=qu.correct.length;
    const expected=Number(qu.expectedCorrectCount);
    const expectedText=`Erwartet ${expected} richtige Antwort(en), erkannt ${actual}.`;
    if(actual!==expected&&!warnings.includes(expectedText)) warnings.push(expectedText);
  }
  return warnings;
}

function showImportWarnings(){
  const qu=q();
  const warnings=importWarnings(qu);

  if(!warnings.length){
    alert('Keine Warnungen vorhanden.');
    return;
  }

  alert(warnings.join('\n'));
}

function importWarningsHtml(qu){
  const warnings=importWarnings(qu);
  if(!warnings.length) return '';
  return `<div class="question-note">Importprüfung: ${warnings.map(esc).join(' ')}</div>`;
}

function cleanRows(qu){return Array.isArray(qu.rows)?qu.rows.map(r=>String(r??'').trim()).filter(Boolean):[]}

function canRenderInputs(qu){
  if(qu.type==='choice') return Array.isArray(qu.options)&&qu.options.length>0;
  if(qu.type==='matrix') return Array.isArray(qu.rows)&&qu.rows.length>0&&Array.isArray(qu.columns)&&qu.columns.length>0;
  if(qu.type==='sequence'){
    const rows=cleanRows(qu);
    const rawRows=Array.isArray(qu.rows)?qu.rows.length:0;
    const values=Array.isArray(qu.values)?qu.values.length:0;
    const completeSolution=!hasSolution(qu)||qu.correct.length===rows.length;
    return rows.length>0&&rows.length===rawRows&&rows.length<=30&&values>0&&values<=30&&completeSolution;
  }
  return false;
}

function render(){
  setModeButtons();
  renderModeActions();
  renderJumpControl();

  if(mode==='editor'){renderEditor(); return;}
  if(examSubmitted){renderExamResult(); return;}

  if(examError){
    document.getElementById('meta').textContent='Prüfungsmodus';
    document.getElementById('app').innerHTML=`<div class="question-note">${esc(examError)}</div><div class="btns"><button onclick="setMode('practice')">Zum Üben</button></div>`;
    return;
  }

  const qu=q();
  document.getElementById('meta').textContent=`${modeLabel()} - Frage ${idx+1} von ${order.length} - Punkte: ${currentScore()}/${totalPoints()}`;

  let html=`<div><span class="pill">${esc(qu.title)}</span>`;
  html+=`<span class="pill">HF ${esc(qu.handlungsfeld??'-')}</span>`;
  html+=`<span class="pill">${qu.points} Punkt${qu.points>1?'e':''}</span><span class="pill">${typeLabel(qu.type)}</span></div>`;
  html+='<div class="trainer"><main class="question-copy">';

  if(questionText(qu)) html+=`<div class="question-text">${esc(questionText(qu))}</div>`;

  html+=`<div class="task-box">${esc(taskText(qu))}</div>`;

  if(!hasTextQuestion(qu)) html+='<div class="question-note">Diese Frage liegt aktuell nur als Bild vor. Für eine barrierearme Ansicht müssen Fragetext und Antworttexte in der JSON ergänzt werden.</div>';
  if(!canRenderInputs(qu)) html+='<div class="question-note">Diese Frage ist noch nicht vollständig als interaktive Textfrage erfasst. Bitte nutze dafür das Originalbild.</div>';
  if(!hasSolution(qu)&&mode==='practice') html+='<div class="question-note">Für diese Zusatzfrage ist noch keine Lösung hinterlegt. Sie wird als Übungsfrage angezeigt und nicht in die Punktewertung einbezogen.</div>';

  html+=importWarningsHtml(qu);

  if(canRenderInputs(qu)) html+=inputHtml(qu);

  html+='<div class="btns">';

  if(mode==='practice'&&hasSolution(qu)&&canRenderInputs(qu)) html+='<button class="good" onclick="check()">Prüfen</button>';

  html+='<button class="secondary" onclick="prev()">Zurück</button><button onclick="next()">Weiter</button>';

  if(mode==='practice'&&hasSolution(qu)) html+='<button class="warn" onclick="showSolution()">Lösung anzeigen</button>';

  html+='</div><div id="result" class="result"></div></main>';

  if(qu.image || qu.answerImage){

    html+=`
      <div class="image-tabs">

        <div class="image-tab-buttons">
    `;

    if(qu.image){
      html+=`
        <button class="secondary active"
                id="tabQuestion"
                onclick="showImageTab('question')">
          Originalbild
        </button>
      `;
    }

    if(mode==='practice' && qu.answerImage){
      html+=`
        <button class="secondary ${!qu.image ? 'active' : ''}"
                id="tabAnswer"
                onclick="showImageTab('answer')">
          Lösungsbild
        </button>
      `;
    }

    html+=`</div>`;

    if(qu.image){
      html+=`
        <div id="questionTab"
            class="image-tab-content"
            style="display:none;">
          <img class="question-img"
              src="${esc(qu.image)}"
              alt="${esc(qu.title)}">
        </div>
      `;
    }

    if(mode==='practice' && qu.answerImage){
      html+=`
        <div id="answerTab"
            class="image-tab-content"
            style="display:none;">
          <img class="question-img"
              src="${esc(qu.answerImage)}"
              alt="Lösungsbild ${esc(qu.title)}">
        </div>
      `;
    }

    html+='</div>';
  }

  html+='</div>';

  document.getElementById('app').innerHTML=html;
  restoreAnswer();
}

function renderModeActions(){
  const el=document.getElementById('modeActions');
  if(!el) return;

  if(mode==='practice'){
    el.innerHTML=`
      <div id="jump" class="jump-control"></div>
      <button class="secondary" onclick="shuffleQuestions()">Mischen</button>
      <button class="danger" onclick="resetProgress()">Zurücksetzen</button>
    `;
  }

  else if(mode==='exam'){
    el.innerHTML=`
      <button class="good" onclick="submitExam()">Prüfung abgeben</button>
      <button class="danger" onclick="setMode('exam')">Neue Prüfung starten</button>
    `;
  }

  else if(mode==='editor'){
    el.innerHTML=`
      <div id="jump" class="jump-control"></div>
      <button class="warn" onclick="showImportWarnings()">Warnungen</button>
    `;
  }
}

function renderJumpControl(){
  const el=document.getElementById('jump');
  if(!el) return;
  if(!data||mode==='exam'){el.innerHTML=''; return;}

  el.innerHTML='<label for="jumpQuestion" class="muted">Frage</label><input id="jumpQuestion" type="number" min="1" placeholder="Nr."><button class="secondary" onclick="jumpToQuestion()">Aufrufen</button>';

  document.getElementById('jumpQuestion').onkeydown=event=>{
    if(event.key==='Enter') jumpToQuestion();
  };
}

function jumpToQuestion(){
  const input=document.getElementById('jumpQuestion');
  const id=Number(input?.value);

  if(!Number.isInteger(id)) return;

  if(mode==='editor') saveEditor(false); else saveAnswer();

  const target=data.questions.findIndex(question=>Number(question.id)===id);

  if(target<0){
    alert('Diese Fragennummer gibt es nicht.');
    return;
  }

  if(mode==='editor'){
    idx=target;
    order=[...Array(data.questions.length).keys()];
    renderEditor();
    return;
  }

  const existing=order.indexOf(target);

  if(existing>=0){
    idx=existing;
  } else {
    order=[...Array(data.questions.length).keys()];
    idx=target;
  }

  render();
}

function modeLabel(){return mode==='exam'?'Prüfungsmodus':'Übungsmodus'}

function taskText(qu){
  if(qu.task) return qu.task;

  if(qu.type==='choice'){
    if(hasSolution(qu)){
      const count=qu.correct.length;
      if(count===1) return 'Aufgabe: Bitte wählen Sie die richtige Antwort aus.';
      return `Aufgabe: Bitte wählen Sie die ${numberWord(count)} richtigen Antworten aus.`;
    }
    return 'Aufgabe: Bitte wählen Sie die richtigen Antworten aus.';
  }

  if(qu.type==='matrix') return 'Aufgabe: Bitte füllen Sie die Kästchen des Rasters aus.';

  return 'Aufgabe: Bitte ordnen Sie die Antworten richtig zu.';
}

function numberWord(n){return ({2:'zwei',3:'drei',4:'vier',5:'fünf',6:'sechs',7:'sieben',8:'acht'}[n]||String(n))}

function setModeButtons(){
  const practice=document.getElementById('practiceBtn');
  const exam=document.getElementById('examBtn');
  const editor=document.getElementById('editorBtn');

  if(!practice||!exam||!editor) return;

  practice.className=mode==='practice'?'active':'secondary';
  exam.className=mode==='exam'?'active':'secondary';
  editor.className=mode==='editor'?'active':'secondary';
}

function typeLabel(t){return t==='choice'?'Auswahlfrage':t==='matrix'?'Rasterfrage':'Zuordnungs-/Reihenfolgefrage'}

function inputHtml(qu){
  if(qu.type==='choice'){
    const options=Array.isArray(qu.options)?qu.options:[];
    const count=Math.max(qu.optionCount||0,options.length);
    let h='<div class="answers">';

    for(let i=1;i<=count;i++){
      const label=letters[i-1]||String(i);
      const text=options[i-1]||`Antwort ${i}`;
      h+=`<label class="answer-row"><input type="checkbox" value="${i}" onchange="saveAnswer()"><span class="answer-label">${label}</span><span class="answer-text">${esc(text)}</span></label>`;
    }

    return h+'</div>';
  }

  if(qu.type==='sequence'){
    let vals=qu.values||[1,2,3,4,5,6,7,8];
    let rows=cleanRows(qu);
    let h='<div class="answers grid">';

    rows.forEach((row,i)=>{
      h+=`<label class="answer-row"><span class="answer-text">${esc(row)}: <select data-pos="${i+1}" onchange="saveAnswer()"><option value="">--</option>${vals.map(v=>`<option>${esc(v)}</option>`).join('')}</select></span></label>`;
    });

    return h+'</div>';
  }

  let h='<div class="answers">';

  qu.rows.forEach((r,i)=>{
    h+=`<label class="answer-row"><span class="answer-text">${i+1}. ${esc(r)}: <select data-pos="${i+1}" onchange="saveAnswer()"><option value="">--</option>${qu.columns.map((c,j)=>`<option value="${j+1}">${esc(c)}</option>`).join('')}</select></span></label>`;
  });

  return h+'</div>';
}

function selected(){
  const qu=q();

  if(qu.type==='choice'){
    return [...document.querySelectorAll('input:checked')].map(e=>+e.value).sort((a,b)=>a-b);
  }

  return [...document.querySelectorAll('select')].map(e=>e.value?+e.value:null);
}

function saveAnswer(){
  answers[key()]=selected();
}

function restoreAnswer(){
  const saved=answers[key()];
  if(!saved) return;

  const qu=q();

  if(qu.type==='choice'){
    document.querySelectorAll('input[type="checkbox"]').forEach(e=>{
      e.checked=saved.includes(+e.value);
    });
    return;
  }

  document.querySelectorAll('select').forEach((e,i)=>{
    e.value=saved[i]??'';
  });
}

function equal(a,b){
  return JSON.stringify(a)===JSON.stringify(b);
}

function check(){
  saveAnswer();

  const qu=q();
  const s=answers[key()];
  const el=document.getElementById('result');

  if(!hasSolution(qu)){
    el.className='result';
    el.textContent='Für diese Frage ist keine Lösung hinterlegt.';
    return;
  }

  const ok=equal(s,qu.correct);

  practiceResults[key()]=ok;

  highlightAnswers(qu, s);

  if(ok){
    el.className='result ok';
    el.textContent='Richtig.';
  } else {
    el.className='result bad';
    el.textContent='Noch nicht richtig.';
  }

  updateMeta();
}

function fmt(a,qu=q()){
  const values=a.map(x=>{
    if(x===null) return '-';
    if(qu.type==='choice') return letters[x-1]||String(x);
    return x;
  });

  return values.join(', ');
}

function showSolution(){
  const qu=q();

  document.getElementById('result').className='result';
  document.getElementById('result').textContent=hasSolution(qu)
    ? 'Lösung: '+fmt(qu.correct)+(qu.explanation?' - '+qu.explanation:'')
    : 'Für diese Frage ist keine Lösung hinterlegt.';
}

function openEditor(){
  const password=prompt('Editor-Kennwort');

  if(password!==EDITOR_PASSWORD){
    alert('Falsches Kennwort.');
    return;
  }

  mode='editor';
  idx=0;
  order=[...Array(data.questions.length).keys()];
  render();
}

function renderEditor(){
  const qu=q();

  document.getElementById('meta').textContent=`Editormodus - Frage ${idx+1} von ${order.length}`;

  let html=`<div><span class="pill">${esc(qu.title)}</span><span class="pill">ID ${esc(qu.id)}</span><span class="pill">HF ${esc(qu.handlungsfeld??'-')}</span>`;

  if(qu.manualEdited) html+='<span class="pill">manuell editiert</span>';

  html+='</div><div class="editor-grid"><main class="editor-form">';
  html+=importWarningsHtml(qu);
  html+=`<div class="field"><label for="editorQuestion">Fragetext</label><textarea id="editorQuestion">${esc(questionText(qu))}</textarea></div>`;
  html+=editorAnswerFields(qu);
  html+='<div class="btns"><button class="good" onclick="saveEditor()">Änderungen übernehmen</button><button class="secondary" onclick="editorPrev()">Zurück</button><button onclick="editorNext()">Weiter</button><button class="warn" onclick="exportQuestionsJson()">questions.json exportieren</button><button class="warn" onclick="exportQuestionsJs()">questions.js exportieren</button></div>';
  html+='<div id="editorResult" class="result"></div></main><aside class="image-panel">';
  html+='<details open><summary>Lösungsbogen</summary>';
  html+=qu.answerImage?`<img class="question-img" src="${esc(qu.answerImage)}" alt="Lösungsbogen ${esc(qu.title)}">`:'<div class="question-note">Für diese Frage ist kein separates Lösungsbogen-Bild hinterlegt.</div>';
  html+=`<div class="question-note">Lösung laut JSON: ${hasSolution(qu)?esc(fmt(qu.correct,qu)):'nicht hinterlegt'}</div></details>`;
  html+=`<details><summary>Originalbild</summary>${qu.image?`<img class="question-img" src="${esc(qu.image)}" alt="${esc(qu.title)}">`:'<div class="question-note">Kein Originalbild hinterlegt.</div>'}</details>`;
  html+='</aside></div>';

  document.getElementById('app').innerHTML=html;
}

function editorAnswerFields(qu){
  if(qu.type==='choice'){
    const options=Array.isArray(qu.options)?qu.options:[];
    let h='<div class="field"><label>Antworten</label>';

    options.forEach((option,i)=>{
      const checked=Array.isArray(qu.correct)&&qu.correct.includes(i+1)?' checked':'';
      h+=`<div class="option-edit"><label><input type="checkbox" class="editor-correct" data-index="${i+1}"${checked}> ${letters[i]||i+1}</label><textarea class="editor-option">${esc(option)}</textarea><div class="option-tools"><button type="button" class="secondary" onclick="moveOption(${i},-1)">↑</button><button type="button" class="secondary" onclick="moveOption(${i},1)">↓</button><button type="button" class="warn" onclick="removeOption(${i})">Entfernen</button></div></div>`;
    });

    h+='<button type="button" class="secondary" onclick="addOption()">Antwort hinzufügen</button></div>';

    return h;
  }

  if(qu.type==='sequence'){
    return `<div class="field"><label for="editorRows">Zeilen</label><textarea id="editorRows">${esc((qu.rows||[]).join('\n'))}</textarea></div><div class="field"><label for="editorCorrect">Lösung, kommasepariert</label><input id="editorCorrect" type="text" value="${esc((qu.correct||[]).join(', '))}"></div>`;
  }

  return `<div class="field"><label for="editorRows">Rasterzeilen</label><textarea id="editorRows">${esc((qu.rows||[]).join('\n'))}</textarea></div><div class="field"><label for="editorCorrect">Lösung, kommasepariert</label><input id="editorCorrect" type="text" value="${esc((qu.correct||[]).join(', '))}"></div>`;
}

function saveEditor(showMessage=true){
  const qu=q();

  qu.question=document.getElementById('editorQuestion').value;

  if(qu.type==='choice'){
    const options=[...document.querySelectorAll('.editor-option')].map(item=>item.value.trim()).filter(Boolean);
    const correct=[...document.querySelectorAll('.editor-correct')].filter(item=>item.checked).map(item=>+item.dataset.index).filter(i=>i<=options.length).sort((a,b)=>a-b);

    qu.options=options;
    qu.optionCount=options.length;
    qu.correct=correct;
    qu.solutionAvailable=correct.length>0;
  } else {
    const rows=(document.getElementById('editorRows')?.value||'').split(/\n+/).map(item=>item.trim()).filter(Boolean);
    const correct=(document.getElementById('editorCorrect')?.value||'').split(',').map(item=>item.trim()).filter(Boolean).map(Number);

    qu.rows=rows;
    qu.optionCount=rows.length;
    qu.values=qu.values&&qu.values.length?qu.values:[...Array(rows.length)].map((_,i)=>i+1);
    qu.correct=correct;
    qu.solutionAvailable=correct.length>0;
  }

  qu.manualEdited=true;
  qu.manualEditedAt=new Date().toISOString();

  if(showMessage){
    document.getElementById('editorResult').textContent='Änderung übernommen. Exportiere anschließend questions.json und questions.js.';
  }
}

function remapCorrectAfterMove(correct, from, to){
  return (correct||[]).map(value=>{
    const index=value-1;

    if(index===from) return to+1;
    if(from<to&&index>from&&index<=to) return index;
    if(to<from&&index>=to&&index<from) return index+2;

    return value;
  }).sort((a,b)=>a-b);
}

function moveOption(index,delta){
  saveEditor(false);

  const qu=q();
  const to=index+delta;

  if(!Array.isArray(qu.options)||to<0||to>=qu.options.length) return;

  [qu.options[index],qu.options[to]]=[qu.options[to],qu.options[index]];
  qu.correct=remapCorrectAfterMove(qu.correct,index,to);

  renderEditor();
}

function addOption(){
  saveEditor(false);

  const qu=q();

  qu.options=Array.isArray(qu.options)?qu.options:[];
  qu.options.push('');
  qu.optionCount=qu.options.length;

  renderEditor();
}

function removeOption(index){
  saveEditor(false);

  const qu=q();

  qu.options.splice(index,1);
  qu.correct=(qu.correct||[]).filter(value=>value!==index+1).map(value=>value>index+1?value-1:value);
  qu.optionCount=qu.options.length;

  renderEditor();
}

function editorNext(){
  saveEditor(false);

  if(idx<order.length-1){
    idx++;
    renderEditor();
  }
}

function editorPrev(){
  saveEditor(false);

  if(idx>0){
    idx--;
    renderEditor();
  }
}

function exportQuestionsJson(){
  saveEditor(false);
  downloadFile('questions.json', JSON.stringify(data,null,2)+'\n', 'application/json');
}

function exportQuestionsJs(){
  saveEditor(false);
  downloadFile('questions.js', 'window.QUESTIONS_DATA = '+JSON.stringify(data,null,2)+';\n', 'text/javascript');
}

function downloadFile(filename,content,type){
  const blob=new Blob([content],{type});
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a');

  link.href=url;
  link.download=filename;
  link.click();

  URL.revokeObjectURL(url);
}

function next(){
  saveAnswer();

  if(idx<order.length-1){
    idx++;
    render();
  }
}

function prev(){
  saveAnswer();

  if(idx>0){
    idx--;
    render();
  }
}

function shuffleQuestions(){
  saveAnswer();

  if(mode==='exam'){
    resetProgress();
    return;
  }

  shuffleArray(order);
  idx=0;
  render();
}

function setMode(nextMode){
  mode=nextMode;
  resetProgress();
}

function resetProgress(){
  idx=0;
  answers={};
  practiceResults={};
  examSubmitted=false;
  examError='';

  if(mode==='exam'){
    order=buildExamOrder();

    if(!order.length){
      examError='Es konnte keine Prüfung mit 48 Fragen und exakt 100 Punkten zusammengestellt werden.';
    }
  } else {
    order=[...Array(data.questions.length).keys()];
  }

  render();
}

function shuffleArray(items){
  for(let i=items.length-1;i>0;i--){
    let j=Math.floor(Math.random()*(i+1));
    [items[i],items[j]]=[items[j],items[i]];
  }

  return items;
}

function buildExamOrder(){
  const targetCount=48;
  const targetPoints=100;
  const candidates=shuffleArray([...Array(data.questions.length).keys()].filter(i=>hasSolution(data.questions[i])&&canRenderInputs(data.questions[i])));
  const states=new Map([['0|0',null]]);

  for(const questionIndex of candidates){
    const points=data.questions[questionIndex].points;
    const snapshot=[...states.keys()];

    for(const state of snapshot){
      const [count,sum]=state.split('|').map(Number);
      const nextCount=count+1;
      const nextSum=sum+points;
      const nextKey=`${nextCount}|${nextSum}`;

      if(nextCount>targetCount||nextSum>targetPoints||states.has(nextKey)) continue;

      states.set(nextKey,{prev:state,questionIndex});
    }
  }

  const endKey=`${targetCount}|${targetPoints}`;

  if(!states.has(endKey)) return [];

  const selected=[];

  for(let state=endKey; state!=='0|0';){
    const entry=states.get(state);
    selected.push(entry.questionIndex);
    state=entry.prev;
  }

  return shuffleArray(selected);
}

function currentScore(){
  if(!data) return 0;

  if(mode==='exam'){
    return examSubmitted
      ? order.reduce((s,i)=>s+(equal(answers[String(i)]||[],data.questions[i].correct)?data.questions[i].points:0),0)
      : 0;
  }

  return Object.entries(practiceResults).reduce((s,[i,ok])=>ok?s+data.questions[+i].points:s,0);
}

function totalPoints(){
  return data?order.reduce((s,i)=>hasSolution(data.questions[i])?s+data.questions[i].points:s,0):0;
}

function updateMeta(){
  document.getElementById('meta').textContent=`${modeLabel()} - Frage ${idx+1} von ${order.length} - Punkte: ${currentScore()}/${totalPoints()}`;
}

function submitExam(){
  saveAnswer();
  examSubmitted=true;
  render();
}

function renderExamResult(){
  const max=totalPoints();
  const score=currentScore();
  const percent=max?Math.round(score/max*100):0;

  let html=`<div><span class="pill">Prüfungsergebnis</span><span class="pill">${score}/${max} Punkte</span><span class="pill">${percent}%</span></div>`;
  html+=`<h2>Auswertung</h2><p class="result ${percent>=50?'ok':'bad'}">Du hast ${score} von ${max} Punkten erreicht.</p>`;
  html+='<div class="summary-list">';

  order.forEach((i,n)=>{
    const qu=data.questions[i];
    const s=answers[String(i)]||[];
    const ok=equal(s,qu.correct);

    html+=`<div class="summary-row"><strong>${n+1}. ${esc(qu.title)}:</strong> <span class="${ok?'ok':'bad'}">${ok?'richtig':'falsch'}</span><br>Deine Antwort: ${esc(fmt(s,qu)||'-')}<br>Lösung: ${esc(fmt(qu.correct,qu))}</div>`;
  });

  html+='</div>';

  document.getElementById('meta').textContent=`Prüfungsmodus - Ergebnis ${score}/${max} Punkte`;
  document.getElementById('app').innerHTML=html;
}

function highlightAnswers(qu, selectedAnswers){

  if(qu.type!=='choice') return;

  const rows=[...document.querySelectorAll('.answer-row')];

  rows.forEach((row,index)=>{

    row.classList.remove('correct','wrong','missed');

    const value=index+1;

    const isCorrect=qu.correct.includes(value);
    const isSelected=selectedAnswers.includes(value);

    if(isCorrect && isSelected){
      row.classList.add('correct');
    }

    else if(!isCorrect && isSelected){
      row.classList.add('wrong');
    }

    else if(isCorrect && !isSelected){
      row.classList.add('missed');
    }

  });
}

function showSolution(){

  const qu=q();

  highlightAnswers(qu, []);

  document.getElementById('result').className='result';

  document.getElementById('result').textContent=
    hasSolution(qu)
      ? 'Die richtigen Antworten sind markiert.'
      : 'Für diese Frage ist keine Lösung hinterlegt.';
}

let currentImageTab = null;

function showImageTab(tab){

  const questionTab=document.getElementById('questionTab');
  const answerTab=document.getElementById('answerTab');

  const questionBtn=document.getElementById('tabQuestion');
  const answerBtn=document.getElementById('tabAnswer');

  const sameTab = currentImageTab === tab;

  // alles ausblenden
  if(questionTab) questionTab.style.display='none';
  if(answerTab) answerTab.style.display='none';

  if(questionBtn) questionBtn.classList.remove('active');
  if(answerBtn) answerBtn.classList.remove('active');

  // gleicher Tab erneut angeklickt -> komplett schließen
  if(sameTab){
    currentImageTab = null;
    return;
  }

  // neuen Tab anzeigen
  currentImageTab = tab;

  if(tab==='question'){
    if(questionTab) questionTab.style.display='block';
    if(questionBtn) questionBtn.classList.add('active');
  }

  if(tab==='answer'){
    if(answerTab) answerTab.style.display='block';
    if(answerBtn) answerBtn.classList.add('active');
  }
}
