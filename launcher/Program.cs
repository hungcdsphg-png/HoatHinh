// Xưởng Video Sản Phẩm — cửa sổ app Windows (WebView2) có logo riêng trên thanh tác vụ.
// Tự bật máy chủ Python (server.py) ẩn, mở giao diện trong cửa sổ, đóng cửa sổ là tắt máy chủ.
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

class MainForm : Form
{
    readonly WebView2 web = new WebView2 { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.FromArgb(14, 20, 27) };
    readonly Label wait = new Label { Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter, Font = new Font("Segoe UI", 14f), ForeColor = Color.FromArgb(200, 210, 220), Text = "Đang khởi động HL Studio…" };
    Process server;
    readonly string appDir;

    public MainForm()
    {
        // exe nằm trong <app>\bin → thư mục app là thư mục cha
        var exeDir = AppContext.BaseDirectory.TrimEnd('\\', '/');
        appDir = File.Exists(Path.Combine(exeDir, "server.py")) ? exeDir : Directory.GetParent(exeDir)!.FullName;
        Text = "HL Studio — Hoàn Lê";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        StartPosition = FormStartPosition.CenterScreen;
        // Cửa sổ rộng đủ chỗ cho khung AI Agent bên phải; tự vừa theo màn hình, màn nhỏ thì mở toàn màn hình.
        var wa = Screen.PrimaryScreen?.WorkingArea ?? new Rectangle(0, 0, 1920, 1040);
        Size = new Size(Math.Max(1100, Math.Min(1860, wa.Width - 40)), Math.Max(700, Math.Min(1020, wa.Height - 30)));
        if (wa.Width < 1500 || wa.Height < 820) WindowState = FormWindowState.Maximized;
        MinimumSize = new Size(1100, 700);
        BackColor = Color.FromArgb(14, 20, 27);
        Controls.Add(web);
        Controls.Add(wait);
        wait.BringToFront();
        Load += async (_, __) => await StartAsync();
        FormClosed += (_, __) => StopServer();
    }

    static string FindPython(string appDir)
    {
        var list = new List<string>
        {
            Path.Combine(appDir, ".venv", "Scripts", "pythonw.exe"),  // bản cài cho khách: Python riêng của app (CAI-DAT.bat tạo)
            Path.Combine(appDir, "..", "video-bang-trang", ".venv", "Scripts", "pythonw.exe"),
            Path.Combine(appDir, "..", "video-bang-trang-pro", ".venv", "Scripts", "pythonw.exe"),
        };
        foreach (var d in "GDCEFH") list.Add($@"{d}:\video-bang-trang\.venv\Scripts\pythonw.exe");
        foreach (var p in list) { try { var f = Path.GetFullPath(p); if (File.Exists(f)) return f; } catch { } }
        foreach (var dir in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            try { var f = Path.Combine(dir.Trim(), "pythonw.exe"); if (File.Exists(f)) return f; } catch { }
        }
        return null;
    }

    static int FreePort()
    {
        var l = new TcpListener(IPAddress.Loopback, 0); l.Start();
        int p = ((IPEndPoint)l.LocalEndpoint).Port; l.Stop(); return p;
    }

    async Task StartAsync()
    {
        var py = FindPython(appDir);
        if (py == null)
        {
            wait.Text = "Không tìm thấy Python của Video Bảng Trắng.\nHãy cài Video Bảng Trắng trước (app dùng chung Python, giọng VieNeu và FFmpeg).";
            return;
        }
        int port = FreePort();
        var psi = new ProcessStartInfo(py, $"\"{Path.Combine(appDir, "server.py")}\" --no-window")
        {
            WorkingDirectory = appDir, UseShellExecute = false, CreateNoWindow = true,
        };
        psi.Environment["VSP_PORT"] = port.ToString();
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        try { server = Process.Start(psi); }
        catch (Exception ex) { wait.Text = "Không chạy được máy chủ: " + ex.Message; return; }

        string url = $"http://127.0.0.1:{port}/";
        using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
        bool up = false;
        for (int i = 0; i < 120 && !up; i++)
        {
            try { var r = await http.GetAsync(url + "api/ping"); up = r.IsSuccessStatusCode; } catch { }
            if (!up) { if (server.HasExited) break; await Task.Delay(500); }
        }
        if (!up)
        {
            wait.Text = "Máy chủ chưa chạy được.\nBấm CHAY-CO-CUA-SO-DEN.bat trong thư mục app để xem lỗi, chụp gửi Hoàn Lê.";
            return;
        }
        try
        {
            var data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "XuongVideoSanPham", "WebView2");
            var env = await CoreWebView2Environment.CreateAsync(null, data, new CoreWebView2EnvironmentOptions("--autoplay-policy=no-user-gesture-required"));
            await web.EnsureCoreWebView2Async(env);
            var s = web.CoreWebView2.Settings;
            s.AreDevToolsEnabled = true; s.IsStatusBarEnabled = false; s.AreDefaultContextMenusEnabled = true; s.IsZoomControlEnabled = true;
            web.CoreWebView2.DocumentTitleChanged += (_, __) => { };
            web.CoreWebView2.NewWindowRequested += (_, e) => { e.Handled = true; try { Process.Start(new ProcessStartInfo(e.Uri) { UseShellExecute = true }); } catch { } };
            // cầu nối với giao diện: mở thư mục / chọn thư mục bằng cửa sổ Windows (nổi lên trên app)
            // cho phép micro (ghi âm giọng đọc)
            web.CoreWebView2.PermissionRequested += (_, e) => { if (e.PermissionKind == CoreWebView2PermissionKind.Microphone) e.State = CoreWebView2PermissionState.Allow; };
            web.CoreWebView2.WebMessageReceived += (_, e) => {
                try {
                    using var doc = System.Text.Json.JsonDocument.Parse(e.WebMessageAsJson);
                    var r = doc.RootElement;
                    if (r.TryGetProperty("open", out var op)) {
                        var path = op.GetString() ?? "";
                        if (File.Exists(path)) Process.Start("explorer.exe", "/select,\"" + path + "\"");
                        else if (Directory.Exists(path)) Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
                    }
                    if (r.TryGetProperty("pickFolder", out var pf)) {
                        using var dlg = new FolderBrowserDialog { Description = "Chọn thư mục lưu video", UseDescriptionForTitle = true, ShowNewFolderButton = true, SelectedPath = pf.GetString() ?? "" };
                        var got = dlg.ShowDialog(this) == DialogResult.OK ? dlg.SelectedPath : "";
                        web.CoreWebView2.PostWebMessageAsJson(System.Text.Json.JsonSerializer.Serialize(new { picked = got }));
                    }
                } catch { }
            };
            web.Source = new Uri(url);
            web.NavigationCompleted += (_, __) => wait.Visible = false;
        }
        catch (WebView2RuntimeNotFoundException)
        {
            wait.Text = "Máy thiếu Microsoft Edge WebView2 Runtime.\nTải miễn phí tại: https://go.microsoft.com/fwlink/p/?LinkId=2124703";
        }
        catch (Exception ex) { wait.Text = "Lỗi mở giao diện: " + ex.Message; }
    }

    void StopServer()
    {
        try { if (server != null && !server.HasExited) server.Kill(true); } catch { }
    }
}
