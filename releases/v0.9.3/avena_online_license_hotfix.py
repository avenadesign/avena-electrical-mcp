"""Avena Electrical 0.9.3: mandatory server-code authentication for every GUI launch."""
from pathlib import Path
import re
root=Path(__file__).resolve().parent
app=root/'app'
def replace(path,old,new):
    s=path.read_text(encoding='utf8')
    if new in s:return
    if s.count(old)!=1:raise RuntimeError(f'Unsupported source: {path.name}')
    path.write_text(s.replace(old,new,1),encoding='utf8')
cloud=app/'cloud_agent.py'; gate=app/'activation_gate.py';gui=app/'gui.py'
if not all(p.exists() for p in (cloud,gate,gui)):
    raise SystemExit('Place patch next to RUN.bat in Avena Electrical 0.9.1+ source folder.')
replace(cloud,'    if existing:\n        try:', '    if existing and not code:\n        try:')
replace(cloud,"    state['encrypted_token'] = _dpapi(token.encode('ascii'), False).hex()", "    verified=cloud_request('GET','/agent/status',token=token,timeout=12)\n    if not verified.get('paired') or verified.get('connection_id') != data.get('pairing_id','')[:8]:\n        raise RuntimeError('Server rejected activation identity')\n    state['encrypted_token'] = _dpapi(token.encode('ascii'), False).hex()")
replace(gate,'پس از اولین فعال‌سازی، اتصال خودکار است و کد دوباره خواسته نمی‌شود.', 'در هر اجرا کد در سرور آونا بررسی می‌شود؛ توکن ویندوز مجوز ورود آفلاین نیست.')
replace(gate,'        self.set_busy(True,"در حال بررسی فعال‌سازی ذخیره‌شده ...")\n        threading.Thread(target=self.check_saved,daemon=True).start()', '        self.set_busy(False,"برای ورود، کد لایسنس آنلاین را وارد کن.")')
replace(gate,'                activated_token(code)\n                self.root.after(0,self.finish)', '''                token=activated_token(code)
                from app.cloud_agent import cloud_request
                status=cloud_request('GET','/agent/status',token=token,timeout=12)
                if not status.get('paired') or not status.get('connection_id'):
                    raise RuntimeError('Online license rejected')
                cid=status['connection_id']
                self.root.after(0,lambda:self.finish(cid))''')
replace(gate,'    def finish(self):','    def finish(self, connection_id=None):')
replace(gate,'        self.on_success()','        self.on_success(connection_id)')
replace(gui, '    def _license_accepted(self):\n        self._licensed = True\n        self.license_label_text.set("● لایسنس دستگاه فعال است")', '    def _license_accepted(self,connection_id=None):\n        self._licensed = True\n        self.license_label_text.set("● ورود آنلاین: "+(connection_id or "نامشخص"))')
replace(gui, '        self.button(left,"وب‌سایت",lambda:webbrowser.open(DOMAIN)).pack(side="left")', '        self.button(left,"وب‌سایت",lambda:webbrowser.open(DOMAIN)).pack(side="left")\n        self.button(left,"تغییر لایسنس",self.change_license).pack(side="left",padx=(8,0))')
replace(gui,'    def _auto_connect(self):', '''    def change_license(self):
        if not messagebox.askyesno('تغییر لایسنس','ارتباط فعلی قطع و کد دوباره آنلاین بررسی شود؟',parent=self.root):return
        self.stop()
        self._licensed=False
        self._cloud_manual_stop=True
        self.license_label_text.set('ورود آنلاین لازم است')
        self._show_license_gate()

    def _auto_connect(self):''')
p=app/'__init__.py'
s=p.read_text(encoding='utf8')
p.write_text(re.sub(r'__version__\s*=\s*"[^"]+"','__version__ = "0.9.3"',s,count=1),encoding='utf8')
print('AVENA ONLINE LOGIN: installed. Close and restart RUN.bat; enter same code as ChatGPT.')
