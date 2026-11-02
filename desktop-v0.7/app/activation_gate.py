"""Avena v0.7 license-first Tkinter gate. Device secret is stored by Windows DPAPI."""
import tkinter as tk
import threading,urllib.error,webbrowser
from app.cloud_agent import activated_token,has_saved_activation

def format_code(text):
 raw=''.join(c for c in text.strip().upper() if c not in '- \\t\\n')
 if len(raw)!=20 or not raw.isascii() or not raw.isalnum():
  raise ValueError('کد اتصال باید ۲۰ حرف یا عدد باشد.')
 return '-'.join(raw[i:i+4] for i in range(0,20,4))

class ActivationGate:
 def __init__(self,root,*,font,on_success):
  self.root=root;self.font=font;self.on_success=on_success;self.busy=False
  self.window=tk.Toplevel(root);self.window.title('Avena Electrical — فعال‌سازی')
  self.window.configure(bg='#0b1320');self.window.geometry('510x440')
  self.window.minsize(420,400);self.window.transient(root)
  self.window.grab_set();self.window.protocol('WM_DELETE_WINDOW',root.destroy)
  p=tk.Frame(self.window,bg='#0b1320',padx=30,pady=23);p.pack(fill='both',expand=True)
  tk.Label(p,text='آونا الکتریکال',font=(font,22,'bold'),bg='#0b1320',fg='#f2f7ff').pack(anchor='e')
  tk.Label(p,text='فعال‌سازی دستگاه و اتصال خودکار ChatGPT',font=(font,10),bg='#0b1320',fg='#35d3c2').pack(anchor='e',pady=(5,18))
  area=tk.Frame(p,bg='#15243a',padx=19,pady=20,highlightthickness=1,highlightbackground='#34506d');area.pack(fill='both',expand=True)
  tk.Label(area,text='کد لایسنس',font=(font,15,'bold'),bg='#15243a',fg='#f2f7ff').pack(anchor='e')
  tk.Label(area,text='از سایت آونا کد اتصال را بگیر و فقط یک بار وارد کن.\nاز دفعه بعد اتصال به‌صورت خودکار انجام می‌شود.',font=(font,10),bg='#15243a',fg='#a9bed3',justify='right',anchor='e').pack(fill='x',pady=11)
  self.code=tk.StringVar()
  self.entry=tk.Entry(area,textvariable=self.code,bg='#0b1320',fg='white',insertbackground='#35d3c2',bd=0,justify='center',font=('Consolas',15))
  self.entry.pack(fill='x',ipady=13);self.entry.bind('<Return>',lambda e:self.activate())
  self.message=tk.Label(area,text='',bg='#15243a',fg='#a9bed3',font=(font,9));self.message.pack(anchor='e',pady=12)
  self.submit=tk.Button(area,text='فعال‌سازی و ورود',command=self.activate,bg='#35d3c2',fg='#052630',relief='flat',font=(font,11,'bold'),pady=10)
  self.submit.pack(fill='x')
  tk.Button(area,text='دریافت کد در elc.avenaai.ir/connect',command=lambda:webbrowser.open('https://elc.avenaai.ir/connect'),bg='#15243a',fg='#35d3c2',relief='flat',font=(font,10)).pack(anchor='e',pady=(9,0))
  self.entry.focus_set()
  self.set_busy(True,'در حال بررسی فعال‌سازی قبلی...')
  threading.Thread(target=self.check_previous,daemon=True).start()
 def set_busy(self,busy,message):
  self.busy=busy;self.submit.config(state='disabled' if busy else 'normal')
  self.message.config(text=message)
 def check_previous(self):
  try:
   if not has_saved_activation():self.root.after(0,lambda:self.set_busy(False,'لطفاً کد اتصال را وارد کن.'));return
   activated_token()
   self.root.after(0,self.complete)
  except Exception as e:
   self.root.after(0,lambda:self.set_busy(False,'بررسی مجوز انجام نشد؛ کد را وارد یا دوباره امتحان کن.'))
 def activate(self):
  if self.busy:return
  try:code=format_code(self.code.get())
  except ValueError as e:self.set_busy(False,str(e));return
  self.set_busy(True,'در حال فعال‌سازی دستگاه...')
  def worker():
   try:
    activated_token(code);self.root.after(0,self.complete)
   except urllib.error.HTTPError as e:
    msg={401:'کد نامعتبر است.',409:'این کد روی دستگاه دیگری فعال شده.',429:'تعداد تلاش زیاد است.'}.get(e.code,f'خطای سرور {e.code}')
    self.root.after(0,lambda:self.set_busy(False,msg))
   except Exception as e:
    msg='اتصال به سرور برقرار نشد: '+type(e).__name__
    self.root.after(0,lambda:self.set_busy(False,msg))
  threading.Thread(target=worker,daemon=True).start()
 def complete(self):
  self.code.set('');self.window.grab_release();self.window.destroy();self.on_success()
