import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import oss2
import datetime
import random
import string
import pyperclip
from tkinterdnd2 import DND_FILES, TkinterDnD
import webbrowser
from PIL import Image, ImageTk
import requests
from io import BytesIO
import configparser
import os

# 设置配置文件路径
CONFIG_FILE_PATH = 'config.ini'
current_image_index = 0  # 当前图片索引
next_marker = ''  # 用于存储分页的标记
image_urls = []  # 缓存图片URL

# 创建配置文件并写入默认配置（如果文件不存在）
def create_default_config():
    if not os.path.isfile(CONFIG_FILE_PATH):
        config = configparser.ConfigParser()
        config.add_section('oss')
        config.set('oss', 'access_key_id', '000000000000')
        config.set('oss', 'access_key_secret', '00000000000000')
        config.set('oss', 'bucket_name', '000000000')
        config.set('oss', 'endpoint', '00000000000')

        with open(CONFIG_FILE_PATH, 'w') as configfile:
            config.write(configfile)

# 创建默认配置文件
create_default_config()

# 读取配置文件信息
config = configparser.ConfigParser()
config.read(CONFIG_FILE_PATH)

# 获取配置
access_key_id = config.get('oss', 'access_key_id')
access_key_secret = config.get('oss', 'access_key_secret')
bucket_name = config.get('oss', 'bucket_name')
endpoint = config.get('oss', 'endpoint')

# 初始化OSS存储
auth = oss2.Auth(access_key_id, access_key_secret)
bucket = oss2.Bucket(auth, endpoint, bucket_name)

# 测试OSS连接
def test_oss_connection(access_key_id, access_key_secret, bucket_name, endpoint):
    try:
        # 尝试连接到 OSS
        auth = oss2.Auth(access_key_id, access_key_secret)
        bucket = oss2.Bucket(auth, endpoint, bucket_name)
        bucket.get_bucket_info()  # 获取存储空间信息来测试连接
        return True  # 连接成功
    except oss2.exceptions.OssError as e:
        print(f"测试连接到 OSS 失败: {e}")
        return False  # 连接失败

# 保存配置信息到config.ini
def save_config():
    # 更新配置
    config.set('oss', 'access_key_id', entry_access_key_id.get())
    config.set('oss', 'access_key_secret', entry_access_key_secret.get())
    config.set('oss', 'bucket_name', entry_bucket_name.get())
    config.set('oss', 'endpoint', entry_endpoint.get())

    with open(CONFIG_FILE_PATH, 'w') as configfile:
        config.write(configfile)

 # 更新全局变量
        global access_key_id, access_key_secret, bucket_name, endpoint, bucket
        access_key_id = entry_access_key_id.get()
        access_key_secret = entry_access_key_secret.get()
        bucket_name = entry_bucket_name.get()
        endpoint = entry_endpoint.get()
        

    # 测试新的OSS连接
    if test_oss_connection(entry_access_key_id.get(), entry_access_key_secret.get(), entry_bucket_name.get(), entry_endpoint.get()):
        messagebox.showinfo("成功", "配置信息已保存并成功连接到 OSS。")
        
        # 重新初始化OSS存储
        global bucket
        auth = oss2.Auth(entry_access_key_id.get(), entry_access_key_secret.get())
        bucket = oss2.Bucket(auth, entry_endpoint.get(), entry_bucket_name.get())
        print("配置信息已更新。")
    else:
        messagebox.showerror("错误", "连接到 OSS 失败，请检查配置信息。")

# 生成随机文件名后缀
def generate_random_suffix(length=6):
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))

# 复制URL到剪贴板
def copy_to_clipboard(url):
    markdown_format = f"![imag]({url})"
    pyperclip.copy(markdown_format)

def copy_to_clipboardA(url):
    pyperclip.copy(url)

# 上传文件并返回URL
def upload_file(file_path):
    try:
        if file_path:
            # 生成对象名称，使用时间戳和随机数
            current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            random_suffix = generate_random_suffix()
            folder_name = 'images'  # 指定文件夹名称
            object_name = f"{folder_name}/{current_time}_{random_suffix}.jpg"  # 假设上传的是jpg图片

            with open(file_path, 'rb') as file:
                # 上传文件
                bucket.put_object(object_name, file)

            # 设置文件为公共读
            bucket.put_object_acl(object_name, oss2.OBJECT_ACL_PUBLIC_READ)
            
            # 构建访问URL，公开访问的URL无需签名
            url = f"http://{bucket_name}.{endpoint.replace('http://', '')}/{object_name}"

            # 更新GUI窗口显示上传成功后返回的链接
            url_label.config(text=url)
            copy_button.config(state=tk.NORMAL)  # 激活复制按钮
            copy_buttonA.config(state=tk.NORMAL)  # 激活复制按钮
        else:
            print("未选择文件。")
    except oss2.exceptions.OssError as e:
        print(f"上传文件失败: {e}")

# 下载缩略图并显示
def download_thumbnail(url):
    try:
        response = requests.get(url)
        img_data = response.content
        img = Image.open(BytesIO(img_data))
        img.thumbnail((100, 100))  # 缩略图大小
        thumbnail_img = ImageTk.PhotoImage(img)

        # 在GUI中显示缩略图
        thumbnail_label = ttk.Label(images_list_text, image=thumbnail_img)
        thumbnail_label.image = thumbnail_img
        images_list_text.window_create(tk.END, window=thumbnail_label)
        images_list_text.insert(tk.END, "\n")
    except Exception as e:
        print(f"下载缩略图失败: {e}")

# 列出指定文件夹中的所有图片
def list_images_in_folder(folder_name):
    global current_image_index, next_marker, image_urls

    try:
        # 如果当前索引已经超出缓存的图片列表，则从OSS获取新的图片
        if current_image_index >= len(image_urls):
            # 生成文件夹前缀
            prefix = folder_name + '/'

            # 使用 oss2.ObjectIterator 获取下一页的文件
            objects = oss2.ObjectIterator(bucket, prefix=prefix, marker=next_marker, max_keys=1)

            # 清空当前缓存的URL
            image_urls.clear()
            
            # 遍历获取到的对象
            for obj in objects:
                if obj.key.endswith('.jpg') or obj.key.endswith('.png') or obj.key.endswith('.jpeg'):  # 根据需要添加其他图片格式
                    # 构建访问URL，公开访问的URL无需签名
                    url = f"http://{bucket_name}.{endpoint.replace('http://', '')}/{obj.key}"
                    image_urls.append(url)

            # 更新分页标记
            next_marker = objects.next_marker

        # 清空显示区
        images_list_text.delete(1.0, tk.END)

        if image_urls:
            # 显示当前索引的图片
            current_url = image_urls[current_image_index]
            thumbnail_url = f"{current_url}?x-oss-process=image/resize,m_fill,w_100,h_100"
            download_thumbnail(thumbnail_url)

            # 创建下载按钮
            download_button = ttk.Button(images_list_text, text="下载", command=lambda u=current_url: download_file(u))
            images_list_text.window_create(tk.END, window=download_button)
            images_list_text.insert(tk.END, "\n")

            # 创建删除按钮
            delete_button = ttk.Button(images_list_text, text="删除", command=lambda u=current_url.split('/')[-1]: delete_file(u))
            images_list_text.window_create(tk.END, window=delete_button)
            images_list_text.insert(tk.END, "\n")

            # 创建复制原始链接按钮
            copy_original_button = ttk.Button(images_list_text, text="复制原始链接", command=lambda u=current_url: copy_to_clipboardA(u))
            images_list_text.window_create(tk.END, window=copy_original_button)

            # 创建复制 Markdown 链接按钮
            copy_markdown_button = ttk.Button(images_list_text, text="复制Markdown链接", command=lambda u=current_url: copy_to_clipboard(u))
            images_list_text.window_create(tk.END, window=copy_markdown_button)
            images_list_text.insert(tk.END, "\n")

        else:
            print("没有更多图片。")

    except oss2.exceptions.OssError as e:
        print(f"获取文件列表失败: {e}")

# 创建下载文件功能
def download_file(url):
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"下载文件失败: {e}")

# 创建删除文件功能
def delete_file(object_key):
    try:
        bucket.delete_object(object_key)
        print(f"已删除文件 {object_key}")
        list_images_in_folder('images')  # 刷新文件列表显示
    except oss2.exceptions.OssError as e:
        print(f"删除文件失败: {e}")

# 创建上传文件页面
def create_upload_page():
    global url_label, copy_button, copy_buttonA

    for widget in right_frame.winfo_children():
        widget.destroy()
    
    url_label = ttk.Label(right_frame, text="", wraplength=350)
    url_label.pack(pady=10)

    # 创建一个框架用于接收拖放文件
    upload_frame = ttk.Frame(right_frame, width=400, height=300, relief='ridge', borderwidth=2)
    upload_frame.pack(pady=20)

    # 在框架中添加标签显示中文提示
    upload_label = ttk.Button(upload_frame, text="拖拽/选择文件上传", command=lambda: upload_file(filedialog.askopenfilename()))
    upload_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def on_drop(event):
        file_path = event.data
        if file_path:
            upload_file(file_path)

    upload_frame.drop_target_register(DND_FILES)
    upload_frame.dnd_bind('<<Drop>>', on_drop)

    copy_button = ttk.Button(right_frame, text="Markdown链接", command=lambda: copy_to_clipboard(url_label.cget("text")))
    copy_buttonA = ttk.Button(right_frame, text="普通链接", command=lambda: copy_to_clipboardA(url_label.cget("text")))

    copy_button.pack()
    copy_buttonA.pack()

# 更新创建查看存储页面
def create_storage_page():
    global images_list_text, current_image_index

    for widget in right_frame.winfo_children():
        widget.destroy()

    images_list_text = tk.Text(right_frame, wrap=tk.WORD)
    images_list_text.pack(fill=tk.BOTH, expand=True)

    # 按钮用于加载上一张图片
    previous_button = ttk.Button(right_frame, text="上一张", command=load_previous_image)
    previous_button.pack(side=tk.LEFT, padx=10)

    # 按钮用于加载下一张图片
    next_button = ttk.Button(right_frame, text="下一张", command=load_next_image)
    next_button.pack(side=tk.RIGHT, padx=10)

    # 重置索引和分页标记
    current_image_index = 0
    next_marker = ''
    image_urls.clear()

    # 加载初始图片
    list_images_in_folder('images')

# 更新加载下一张图片功能
def load_next_image():
    global current_image_index
    if current_image_index + 1 < len(image_urls):
        current_image_index += 1
        list_images_in_folder('images')
    else:
        messagebox.showinfo("提示", "没有更多图片。")

# 添加加载上一张图片功能
def load_previous_image():
    global current_image_index
    if current_image_index > 0:
        current_image_index -= 1
        list_images_in_folder('images')
    else:
        messagebox.showinfo("提示", "没有更多图片。")

# 创建设置页面
def create_settings_page():
    global entry_access_key_id, entry_access_key_secret, entry_bucket_name, entry_endpoint

    for widget in right_frame.winfo_children():
        widget.destroy()

    # 配置样式
    style = ttk.Style()
    style.configure("TLabel", font=("Arial", 12))
    style.configure("TEntry", font=("Arial", 12))
    # 移除TButton的颜色配置

    # 创建输入框及其标签
    ttk.Label(right_frame, text="Access Key ID:", style="TLabel").grid(row=0, column=0, padx=10, pady=10, sticky="w")
    entry_access_key_id = ttk.Entry(right_frame, style="TEntry")
    entry_access_key_id.insert(0, access_key_id)
    entry_access_key_id.grid(row=0, column=1, padx=10, pady=10)

    ttk.Label(right_frame, text="Access Key Secret:", style="TLabel").grid(row=1, column=0, padx=10, pady=10, sticky="w")
    entry_access_key_secret = ttk.Entry(right_frame, show="*", style="TEntry")
    entry_access_key_secret.insert(0, access_key_secret)
    entry_access_key_secret.grid(row=1, column=1, padx=10, pady=10)

    ttk.Label(right_frame, text="Bucket Name:", style="TLabel").grid(row=2, column=0, padx=10, pady=10, sticky="w")
    entry_bucket_name = ttk.Entry(right_frame, style="TEntry")
    entry_bucket_name.insert(0, bucket_name)
    entry_bucket_name.grid(row=2, column=1, padx=10, pady=10)

    ttk.Label(right_frame, text="Endpoint:", style="TLabel").grid(row=3, column=0, padx=10, pady=10, sticky="w")
    entry_endpoint = ttk.Entry(right_frame, style="TEntry")
    entry_endpoint.insert(0, endpoint)
    entry_endpoint.grid(row=3, column=1, padx=10, pady=10)

    # 保存按钮
    save_button = ttk.Button(right_frame, text="保存配置", command=save_config)
    save_button.grid(row=4, columnspan=2, pady=20)

    # 调整列的大小
    right_frame.grid_columnconfigure(0, weight=1)
    right_frame.grid_columnconfigure(1, weight=3)

# 创建GUI窗口
def create_gui():
    global right_frame, images_list_text

    root = TkinterDnD.Tk()
    root.title("阿里云 OSS 文件上传")
    root.geometry("600x500")

    paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
    paned_window.pack(fill=tk.BOTH, expand=1)

    left_frame = tk.Frame(paned_window)
    paned_window.add(left_frame, width=100)

    separator = ttk.Separator(paned_window, orient='vertical')
    paned_window.add(separator, width=5)

    right_frame = tk.Frame(paned_window)
    paned_window.add(right_frame, width=500)

    upload_page_button = ttk.Button(left_frame, text="上传文件", command=create_upload_page)
    upload_page_button.pack(fill=tk.X, pady=0)

    storage_page_button = ttk.Button(left_frame, text="查看图片", command=create_storage_page)
    storage_page_button.pack(fill=tk.X, pady=0)
    
    get_all_button = ttk.Button(left_frame, text="查看所有", command=get_all_page)
    get_all_button.pack(fill=tk.X, pady=0)

    
    set_account_button = ttk.Button(left_frame, text="设置", command=create_settings_page)
    set_account_button.pack(fill=tk.X, pady=0)
    

    root.mainloop()
def get_all_in_folder(folder_name):
    try:
        # 生成文件夹前缀
        prefix = folder_name + '/'

        # 清空显示区
        images_list_text.delete(1.0, tk.END)

        # 使用 oss2.ObjectIterator 遍历文件夹中的所有对象
        for obj in oss2.ObjectIterator(bucket, prefix=prefix):
            if obj.key.endswith('.jpg') or obj.key.endswith('.png') or obj.key.endswith('.jpeg'):  # 根据需要添加其他图片格式
                # 构建访问URL，公开访问的URL无需签名
                url = f"http://{bucket_name}.{endpoint.replace('http://', '')}/{obj.key}"
                # 下载缩略图并显示
                thumbnail_url = f"http://{bucket_name}.{endpoint.replace('http://', '')}/{obj.key}?x-oss-process=image/resize,m_fill,w_100,h_100"
                download_thumbnail(thumbnail_url)
                
                # 创建下载按钮
                download_button = ttk.Button(images_list_text, text="下载", command=lambda u=url: download_file(u))
                images_list_text.window_create(tk.END, window=download_button)
                images_list_text.insert(tk.END, "\n")

                # 创建删除按钮
                delete_button = ttk.Button(images_list_text, text="删除", command=lambda u=obj.key: delete_file(u))
                images_list_text.window_create(tk.END, window=delete_button)
                images_list_text.insert(tk.END, "\n")

                # 创建复制原始链接按钮
                copy_original_button = ttk.Button(images_list_text, text="复制原始链接", command=lambda u=url: copy_to_clipboardA(u))
                images_list_text.window_create(tk.END, window=copy_original_button)

                # 创建复制 Markdown 链接按钮
                copy_markdown_button = ttk.Button(images_list_text, text="复制Markdown链接", command=lambda u=url: copy_to_clipboard(u))
                images_list_text.window_create(tk.END, window=copy_markdown_button)
                images_list_text.insert(tk.END, "\n")

    except oss2.exceptions.OssError as e:
        print(f"获取文件列表失败: {e}")

# 创建查看存储页面
def get_all_page():
    global images_list_text, scrollbar
    for widget in right_frame.winfo_children():
        widget.destroy()

    list_images_button = ttk.Button(right_frame, text="显示所有图片", command=lambda: get_all_in_folder('images'))
    list_images_button.pack(pady=10)

    scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL)
    images_list_text = tk.Text(right_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
    scrollbar.config(command=images_list_text.yview)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    images_list_text.pack(pady=10, fill=tk.BOTH, expand=True)        
# 调用示例
create_gui()
