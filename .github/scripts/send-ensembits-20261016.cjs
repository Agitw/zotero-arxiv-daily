// One-off topic delivery. Do not rerun after SMTP acceptance.
const fs = require('node:fs');
const tls = require('node:tls');
const crypto = require('node:crypto');
const data = JSON.parse(fs.readFileSync('docs/research/ensembits-2026-10-16.json','utf8'));
const report = fs.readFileSync('docs/research/ensembits-2026-10-16.md','utf8');
const html = fs.readFileSync('docs/research/ensembits-2026-10-16.html','utf8');
for (const name of ['SENDER','RECEIVER','SENDER_PASSWORD']) if (!process.env[name]) throw new Error(`Missing ${name}`);
if (process.env.GITHUB_RUN_ATTEMPT && process.env.GITHUB_RUN_ATTEMPT !== '1') throw new Error('Refusing duplicate workflow attempt; inspect original SMTP outcome');
const sender=process.env.SENDER.trim(), receiver=process.env.RECEIVER.trim();
if ([sender,receiver].some(v=>/[\r\n<>]/.test(v)||!v.includes('@'))) throw new Error('Invalid mailbox format');
if (!data.papers.every(p=>p.score>7)) throw new Error('Strict threshold failed');
const wrap = s => Buffer.from(s,'utf8').toString('base64').match(/.{1,76}/g).join('\r\n');
const alt='alt-'+crypto.randomUUID(), mixed='mixed-'+crypto.randomUUID();
const subject=`ENSEMBITS 专题检索｜${data.papers.length}篇相关度>7｜2024-10-16至2026-10-16`;
function encodedHeader(value){
  const chunks=[];let current='';
  for(const c of value){if(Buffer.byteLength(current+c,'utf8')>30){chunks.push(current);current='';}current+=c;}
  if(current)chunks.push(current);
  return chunks.map(s=>`=?UTF-8?B?${Buffer.from(s).toString('base64')}?=`).join('\r\n ');
}
const messageId=`<ensembits-20261016-${process.env.GITHUB_RUN_ID||crypto.randomUUID()}@zotero-arxiv-daily>`;
const mime=[`From: <${sender}>`,`To: <${receiver}>`,`Subject: ${encodedHeader(subject)}`,`Date: ${new Date().toUTCString()}`,`Message-ID: ${messageId}`,'MIME-Version: 1.0',`Content-Type: multipart/mixed; boundary="${mixed}"`,'',`--${mixed}`,`Content-Type: multipart/alternative; boundary="${alt}"`,'',`--${alt}`,'Content-Type: text/plain; charset=utf-8','Content-Transfer-Encoding: base64','',wrap(report),`--${alt}`,'Content-Type: text/html; charset=utf-8','Content-Transfer-Encoding: base64','',wrap(html),`--${alt}--`,`--${mixed}`,'Content-Type: text/markdown; charset=utf-8; name="ensembits-2026-10-16.md"','Content-Disposition: attachment; filename="ensembits-2026-10-16.md"','Content-Transfer-Encoding: base64','',wrap(report),`--${mixed}--`,''].join('\r\n');
async function main(){
  const socket=tls.connect({host:'smtp.qq.com',port:465,servername:'smtp.qq.com',rejectUnauthorized:true});
  let input='', lines=[], responses=[], waiting=null, failure=null;
  const finish = err => { failure=err; if(waiting){waiting.reject(err);waiting=null;} };
  socket.setTimeout(45000,()=>socket.destroy(new Error('SMTP timeout; do not automatically resend')));
  socket.on('error',finish);
  socket.on('end',()=>finish(new Error('SMTP connection closed')));
  socket.on('data',chunk=>{input+=chunk.toString('utf8');let at;while((at=input.indexOf('\r\n'))>=0){const line=input.slice(0,at);input=input.slice(at+2);lines.push(line);if(/^\d{3} /.test(line)){const reply={code:Number(line.slice(0,3)),lines};lines=[];if(waiting){const w=waiting;waiting=null;w.resolve(reply);}else responses.push(reply);}}});
  const read = () => failure ? Promise.reject(failure) : responses.length ? Promise.resolve(responses.shift()) : new Promise((resolve,reject)=>{waiting={resolve,reject};});
  const expect = async(code)=>{const r=await read();if(r.code!==code)throw new Error(`SMTP expected ${code}, received ${r.code}; response omitted to protect mailbox details`);};
  const command = async(text,code)=>{socket.write(text+'\r\n');await expect(code);};
  try {
    await expect(220);
    await command('EHLO zotero-arxiv-daily',250);
    await command('AUTH LOGIN',334);
    await command(Buffer.from(sender).toString('base64'),334);
    await command(Buffer.from(process.env.SENDER_PASSWORD).toString('base64'),235);
    await command(`MAIL FROM:<${sender}>`,250);
    await command(`RCPT TO:<${receiver}>`,250);
    await command('DATA',354);
    socket.write(mime.replace(/^\./gm,'..')+'\r\n.\r\n');
    await expect(250);
    console.log(`SMTP_ACCEPTED: ${data.papers.length} papers; strict relevance > 7; Message-ID ${messageId}`);
    fs.mkdirSync('outputs',{recursive:true});
    fs.writeFileSync('outputs/ensembits-delivery.json',JSON.stringify({status:'smtp_accepted',count:data.papers.length,threshold:'>7',window:[data.window_start,data.window_end],message_id:messageId,run_id:process.env.GITHUB_RUN_ID,accepted_at:new Date().toISOString()},null,2));
    socket.write('QUIT\r\n');
    socket.end();
  } catch(e) {socket.destroy();throw e;}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
