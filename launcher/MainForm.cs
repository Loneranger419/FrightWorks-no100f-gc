using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Media;

namespace ScoobyReMasked;

// The launcher window: an animated Mystic Manor header in the game's own look (green sky, chimney smoke, firework
// sparkles, the angel fountain, the sign, Scooby Snack S-coins to collect), a nav column where Scooby warps on a
// swirl pad, and one card per page (Play, Display, Controls, Mods). Everything it changes goes to
// data\UserData\Config.toml, the keys the game's F10 menu uses. All art is drawn here; nothing from the game is shipped.
sealed class MainForm : Form
{
    const string GameExe = "Scooby-Doo Refrightened.exe", AppTitle = "Scooby-Doo: Refrightened";
    static Color Hex(string s) => ColorTranslator.FromHtml(s);
    // The game's palette: the logo's purple with its orange-tan rim, Mystic Manor's green sky and amber windows.
    static readonly Color Cream = Hex("#ECEFE4"), Paper = Hex("#FBFCF8"), Ink = Hex("#1F1830"), Teal = Hex("#5E3C91"),
        TealLight = Hex("#E5DCF3"), Lime = Hex("#8CC63F"), Orange = Hex("#E8963A"), Gold = Hex("#F8CB72"), Brown = Hex("#7A5232"),
        Night = Hex("#1D573C"), Dusk = Hex("#5AA57A"), Moon = Hex("#F2F7E8"), Shadow = Hex("#0E1F1A");

    // Fonts are in points and grow with Windows display scaling; every pixel size goes through S() so it grows too.
    static float k = 1f;
    static int S(int v) => (int)Math.Round(v * k);
    static Size S(int w, int h) => new(S(w), S(h));
    static Padding S(int l, int t, int r, int b) => new(S(l), S(t), S(r), S(b));

    readonly string root, play, userData, configPath, modsDir, discDir;
    readonly string? shotDir;
    readonly Panel content = new() { Dock = DockStyle.Fill };
    readonly List<(Button button, Control page)> pages = new();
    Label playStatus = null!, dumpHelp = null!;
    Button chooseDisc = null!, playButton = null!;
    ProgressBar progress = null!;

    public MainForm(string? shotDir = null)
    {
        this.shotDir = shotDir;
        k = DeviceDpi / 96f;
        (root, play) = FindGame();
        userData = Path.Combine(play, "UserData");
        configPath = Path.Combine(userData, "Config.toml");
        modsDir = Path.Combine(userData, "mods");
        // Release: the disc lives in data\Disc next to the game. Dev tree (Play\): the shared Disc\ at the root.
        discDir = IsRelease ? Path.Combine(play, "Disc", "DATA") : Path.Combine(root, "Disc", "DATA");

        Text = AppTitle;
        try { Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!); } catch { }
        glassCursor = MakeGlassCursor(clickable: false);
        glassHand = MakeGlassCursor(clickable: true);
        Cursor = glassCursor;
        var area = Screen.PrimaryScreen?.WorkingArea.Size ?? new Size(S(1060), S(740));
        ClientSize = new Size(Math.Min(S(1060), area.Width - 40), Math.Min(S(740), area.Height - 60));
        MinimumSize = new Size(Math.Min(S(900), area.Width), Math.Min(S(620), area.Height));
        BackColor = Cream;
        Font = new Font("Segoe UI", 10.5f);
        StartPosition = FormStartPosition.CenterScreen;
        DoubleBuffered = true;
        content.Padding = S(16, 12, 20, 16);

        var header = new BufferedPanel { Dock = DockStyle.Top, Height = S(170) };
        header.Paint += PaintHeader;
        var nav = new BufferedFlow { Dock = DockStyle.Left, Width = S(220), FlowDirection = FlowDirection.TopDown, Padding = S(16, 18, 0, 0), WrapContents = false };
        nav.Paint += PaintNav;
        header.MouseClick += (_, e) =>
        {
            for (int i = 0; i < coinRects.Length; i++)
                if (coinRects[i].Contains(e.Location) && Progress("coin" + i, 1.2) < 0) { startAt["coin" + i] = T; snacks++; SystemSounds.Asterisk.Play(); }
        };
        header.MouseMove += (_, e) => header.Cursor = coinRects.Any(c => c.Contains(e.Location)) ? glassHand : glassCursor;
        nav.MouseClick += (_, e) => { if (scoobyRect.Contains(e.Location) && Progress("warp", 1.6) < 0) startAt["warp"] = T; };
        nav.MouseMove += (_, e) => nav.Cursor = scoobyRect.Contains(e.Location) ? glassHand : glassCursor;
        var frame = new System.Windows.Forms.Timer { Interval = 33 };
        frame.Tick += (_, _) =>
        {
            if (!animate || WindowState == FormWindowState.Minimized) return;
            header.Invalidate();
            nav.Invalidate(new Rectangle(0, navSpriteTop, nav.Width, Math.Max(0, nav.Height - navSpriteTop)));
            float glow = (float)(Math.Sin(T * 3) + 1) / 2;  // PLAY breathes between orange and gold
            if (playButton.Enabled) playButton.BackColor = Color.FromArgb(Lerp(Orange.R, Gold.R, glow), Lerp(Orange.G, Gold.G, glow), Lerp(Orange.B, Gold.B, glow));
        };
        frame.Start();
        Controls.Add(content);
        Controls.Add(nav);
        Controls.Add(header);

        AddPage(nav, "Play", BuildPlayPage());
        AddPage(nav, "Display", BuildDisplayPage());
        AddPage(nav, "Controls", BuildControlsPage());
        AddPage(nav, "Mods", BuildModsPage());
        ShowPage(pages[0].button);
        Shown += (_, _) =>
        {
            if (shotDir == null) return;
            // Headless visual check: every page drawn to <dir>\<page>.png, plus the two pointers.
            Directory.CreateDirectory(shotDir);
            shotShift = 9;
            foreach (var p in pages)
            {
                ShowPage(p.button);
                Application.DoEvents();
                using var bmp = new Bitmap(Width, Height);
                DrawToBitmap(bmp, new Rectangle(Point.Empty, Size));
                bmp.Save(Path.Combine(shotDir, p.button.Text + ".png"));
            }
            using (var cur = new Bitmap(S(80), S(40)))
            using (var g = Graphics.FromImage(cur))
            {
                g.Clear(Cream);
                for (int i = 0; i < cursorBitmaps.Count; i++) g.DrawImageUnscaled(cursorBitmaps[i], i * S(40), 0);
                cur.Save(Path.Combine(shotDir, "cursor.png"));
            }
            Close();
        };
    }

    // The game folder: data\ beside the launcher (release), or Play\ above launcher\publish (dev tree).
    static (string root, string game) FindGame()
    {
        for (var d = new DirectoryInfo(AppContext.BaseDirectory); d != null; d = d.Parent)
            foreach (var sub in new[] { "data", "Play" })
                if (File.Exists(Path.Combine(d.FullName, sub, GameExe))) return (d.FullName, Path.Combine(d.FullName, sub));
        return (AppContext.BaseDirectory, Path.Combine(AppContext.BaseDirectory, "data"));
    }

    bool IsRelease => Path.GetFileName(play) == "data";

    void AddPage(FlowLayoutPanel nav, string title, Control page)
    {
        var button = new Button
        {
            Text = title, Size = S(188, 50), FlatStyle = FlatStyle.Flat, BackColor = Paper, ForeColor = Ink,
            Font = new Font("Segoe UI", 13f, FontStyle.Bold), TextAlign = ContentAlignment.MiddleLeft, Padding = S(12, 0, 0, 0),
            Margin = S(0, 0, 0, 10), Cursor = glassHand,
        };
        button.FlatAppearance.BorderColor = Ink;
        button.FlatAppearance.BorderSize = S(2);
        button.Click += (_, _) => ShowPage(button);
        button.MouseEnter += (_, _) => { if (button.BackColor == Paper) button.BackColor = TealLight; };
        button.MouseLeave += (_, _) => { if (button.BackColor == TealLight) button.BackColor = Paper; };
        page.Dock = DockStyle.Fill;
        page.Visible = false;
        content.Controls.Add(page);
        nav.Controls.Add(button);
        pages.Add((button, page));
    }

    void ShowPage(Button button)
    {
        foreach (var (b, page) in pages)
        {
            bool on = b == button;
            b.BackColor = on ? Teal : Paper;
            b.ForeColor = on ? Color.White : Ink;
            page.Visible = on;
        }
        RefreshDisc();
    }

    // ----- The fun bits: animated header and side column -----
    // Everything moves on one clock; with Windows animations turned off the scene stands still.
    readonly bool animate = SystemInformation.UIEffectsEnabled;
    readonly Stopwatch clock = Stopwatch.StartNew();
    double T => (animate ? clock.Elapsed.TotalSeconds : 1.0) + shotShift;
    double shotShift;  // --shots moves the clock on so smoke, sparkles and spray are mid-way
    readonly Dictionary<string, double> startAt = new();
    Bitmap? headerBack, headerFront, headerTitle;
    readonly List<RectangleF> windows = new();
    readonly List<PointF> chimneys = new();
    readonly List<(float x, float y, float r, float phase)> stars = new();
    PointF fountainTop;
    readonly PointF[] coinSpots = new PointF[3];
    readonly Rectangle[] coinRects = new Rectangle[3];
    Rectangle scoobyRect;
    int navSpriteTop, snacks;

    static int Lerp(int a, int b, float f) => (int)(a + (b - a) * f);

    // How far into a click-triggered move (0..1), or -1 when none is playing.
    double Progress(string name, double seconds) => startAt.TryGetValue(name, out var at) && T - at < seconds ? (T - at) / seconds : -1;

    // The pointer: a Scooby Snack S-coin like the ones Scooby collects in the game; a sparkle over anything clickable.
    // Static so Btn() can use it.
    static Cursor glassCursor = Cursors.Default, glassHand = Cursors.Hand;
    readonly List<Bitmap> cursorBitmaps = new();

    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    struct IconInfo { public bool fIcon; public int xHotspot, yHotspot; public IntPtr hbmMask, hbmColor; }
    [System.Runtime.InteropServices.DllImport("user32.dll")] static extern IntPtr CreateIconIndirect(ref IconInfo info);
    [System.Runtime.InteropServices.DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);

    Cursor MakeGlassCursor(bool clickable)
    {
        int size = S(32);
        float c = size * 0.42f;  // coin centre = the click point
        using var bmp = new Bitmap(size, size);
        using (var g = Graphics.FromImage(bmp))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            DrawCoin(g, c, c, size * 0.72f, 1f);
            if (clickable) DrawSparkle(g, size * 0.8f, size * 0.2f, size * 0.22f, Gold);
        }
        var info = new IconInfo { fIcon = false, xHotspot = (int)c, yHotspot = (int)c, hbmColor = bmp.GetHbitmap(Color.FromArgb(0)), hbmMask = new Bitmap(size, size).GetHbitmap() };
        cursorBitmaps.Add((Bitmap)bmp.Clone());
        var h = CreateIconIndirect(ref info);
        DeleteObject(info.hbmColor);
        DeleteObject(info.hbmMask);
        return h == IntPtr.Zero ? (clickable ? Cursors.Hand : Cursors.Default) : new Cursor(h);
    }

    // A Scooby Snack S-coin: a brown biscuit with a raised S. spin (0..1) squeezes it as it turns.
    static void DrawCoin(Graphics g, float cx, float cy, float w, float spin, int alpha = 255)
    {
        float cw = Math.Max(w * 0.12f, w * spin), ch = w * 1.08f;
        var rect = new RectangleF(cx - cw / 2, cy - ch / 2, cw, ch);
        using (var edge = new SolidBrush(Color.FromArgb(alpha, 0x4A, 0x2D, 0x16))) g.FillEllipse(edge, RectangleF.Inflate(rect, w * 0.05f, w * 0.05f));
        using (var face = new LinearGradientBrush(RectangleF.Inflate(rect, 1, 1), Color.FromArgb(alpha, 0xB0, 0x7A, 0x45), Color.FromArgb(alpha, 0x7A, 0x4C, 0x26), LinearGradientMode.ForwardDiagonal))
            g.FillEllipse(face, rect);
        if (spin < 0.35f) return;
        using var f = new Font("Georgia", ch * 0.52f, FontStyle.Bold, GraphicsUnit.Pixel);
        var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
        var state = g.Save();
        g.TranslateTransform(cx, cy);
        g.ScaleTransform(spin, 1);
        using (var dark = new SolidBrush(Color.FromArgb(alpha * 3 / 4, 0x4A, 0x2D, 0x16))) g.DrawString("S", f, dark, w * 0.03f, w * 0.04f, fmt);
        using (var light = new SolidBrush(Color.FromArgb(alpha, 0xD2, 0x9E, 0x63))) g.DrawString("S", f, light, 0, 0, fmt);
        g.Restore(state);
    }

    static void DrawSparkle(Graphics g, float cx, float cy, float s, Color color)
    {
        using var b = new SolidBrush(color);
        g.FillPolygon(b, new[] { new PointF(cx, cy - s), new PointF(cx + s * 0.22f, cy - s * 0.22f), new PointF(cx + s, cy), new PointF(cx + s * 0.22f, cy + s * 0.22f),
                                 new PointF(cx, cy + s), new PointF(cx - s * 0.22f, cy + s * 0.22f), new PointF(cx - s, cy), new PointF(cx - s * 0.22f, cy - s * 0.22f) });
    }

    // The swirl pad Scooby warps on: a stone disc with a spiral, turned by angle.
    static void DrawSwirlPad(Graphics g, float cx, float cy, float rx, float ry, double angle, Color glow)
    {
        using (var stone = new SolidBrush(Hex("#8C979B"))) g.FillEllipse(stone, cx - rx, cy - ry, rx * 2, ry * 2);
        using (var rim = new Pen(Hex("#4F5A5F"), Math.Max(1.5f, rx / 14))) g.DrawEllipse(rim, cx - rx, cy - ry, rx * 2, ry * 2);
        var pts = new List<PointF>();
        for (int i = 0; i <= 60; i++)
        {
            double th = i / 60.0 * Math.PI * 5, rr = 0.08 + 0.8 * i / 60.0;
            pts.Add(new PointF((float)(cx + Math.Cos(th + angle) * rr * rx), (float)(cy + Math.Sin(th + angle) * rr * ry)));
        }
        using var spiral = new Pen(glow, Math.Max(2f, rx / 6)) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
        g.DrawLines(spiral, pts.ToArray());
    }

    // The title face: the embedded title.ttf when the build has one (a Scooby-Doo logo look-alike), else a stock face.
    static readonly System.Drawing.Text.PrivateFontCollection titleFonts = new();
    static FontFamily TitleFont()
    {
        try
        {
            using var s = typeof(MainForm).Assembly.GetManifestResourceStream("ScoobyReMasked.title.ttf");
            if (s != null && titleFonts.Families.Length == 0)
            {
                var data = ReadAll(s);
                var mem = System.Runtime.InteropServices.Marshal.AllocCoTaskMem(data.Length);  // kept for the app's life
                System.Runtime.InteropServices.Marshal.Copy(data, 0, mem, data.Length);
                titleFonts.AddMemoryFont(mem, data.Length);
            }
            if (titleFonts.Families.Length > 0) return titleFonts.Families[0];
        }
        catch { }
        foreach (var name in new[] { "Cooper Black", "Segoe UI Black" })
            if (FontFamily.Families.Any(f => f.Name == name)) return new FontFamily(name);
        return new FontFamily("Segoe UI");
    }

    // Static parts of the header, drawn once per size: the green sky behind; the courtyard, fountain, sign, manor and
    // tree in front; the title on top.
    void BuildHeaderLayers(Size size)
    {
        headerBack?.Dispose();
        headerFront?.Dispose();
        var r = new Rectangle(Point.Empty, size);
        float W = r.Width, ground = r.Height - S(30);
        headerBack = new Bitmap(size.Width, size.Height);
        using (var g = Graphics.FromImage(headerBack))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var sky = new LinearGradientBrush(r, Night, Dusk, LinearGradientMode.Vertical)) g.FillRectangle(sky, r);
            // The long pale streaks across Mystic Manor's sky.
            using (var streak = new SolidBrush(Color.FromArgb(34, 220, 245, 225)))
                foreach (var (x, y, w, h) in new[] { (0.05f, 26f, 0.5f, 10f), (0.35f, 48f, 0.6f, 12f), (0.6f, 20f, 0.45f, 8f), (0.15f, 70f, 0.4f, 9f), (0.7f, 66f, 0.4f, 10f) })
                    g.FillEllipse(streak, W * x, S((int)y), W * w, S((int)h));
        }
        var rng = new Random(11);
        stars.Clear();
        for (int i = 0; i < size.Width / S(24); i++)
            stars.Add((rng.Next(size.Width), rng.Next(S(60)), S(1) + (float)rng.NextDouble() * S(1), (float)rng.NextDouble() * 6));

        headerFront = new Bitmap(size.Width, size.Height);
        windows.Clear();
        chimneys.Clear();
        using (var g = Graphics.FromImage(headerFront))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            // Hedges and cypresses along the courtyard wall.
            using (var hedge = new SolidBrush(Hex("#173A2E")))
            {
                for (float x = 0; x < W; x += S(46)) g.FillEllipse(hedge, x - S(10), ground - S(20), S(66), S(34));
                foreach (float cx in new[] { 0.31f, 0.345f, 0.585f })
                    g.FillPolygon(hedge, new[] { new PointF(W * cx - S(11), ground - S(4)), new PointF(W * cx, ground - S(58)), new PointF(W * cx + S(11), ground - S(4)) });
            }
            // Iron fence with spear tips on the left.
            using (var iron = new Pen(Hex("#0B1512"), S(2)))
            {
                g.DrawLine(iron, 0, ground - S(16), W * 0.3f, ground - S(16));
                for (float x = S(6); x < W * 0.3f; x += S(11))
                {
                    g.DrawLine(iron, x, ground, x, ground - S(22));
                    using var tip = new SolidBrush(Hex("#0B1512"));
                    g.FillPolygon(tip, new[] { new PointF(x - S(3), ground - S(21)), new PointF(x, ground - S(28)), new PointF(x + S(3), ground - S(21)) });
                }
            }
            // The lawn and the pale path that curves up to the door.
            using (var lawn = new SolidBrush(Hex("#16302B"))) g.FillRectangle(lawn, 0, ground, W, r.Height - ground);
            using (var path = new GraphicsPath())
            {
                path.AddBezier(W * 0.22f, r.Height, W * 0.42f, ground + S(16), W * 0.55f, ground + S(4), W * 0.68f, ground);
                path.AddLine(W * 0.68f, ground, W * 0.75f, ground);
                path.AddBezier(W * 0.75f, ground, W * 0.62f, ground + S(10), W * 0.55f, ground + S(22), W * 0.42f, r.Height);
                path.CloseFigure();
                using var stone = new SolidBrush(Hex("#6E7F7C"));
                g.FillPath(stone, path);
            }

            // Mystic Manor: grey-blue clapboard, dark roofs, the round turret with its cone and the octagonal tower.
            float mx = W * 0.745f;
            using var wall = new SolidBrush(Hex("#44515D"));
            using var roof = new SolidBrush(Hex("#1D232B"));
            using var trim = new Pen(Hex("#62717F"), Math.Max(1f, S(1)));
            // The octagonal tower behind.
            g.FillRectangle(wall, mx + S(4), ground - S(104), S(40), S(60));
            g.FillPolygon(roof, new[] { new PointF(mx, ground - S(102)), new PointF(mx + S(8), ground - S(116)), new PointF(mx + S(40), ground - S(116)), new PointF(mx + S(48), ground - S(102)) });
            // The main house, the left gable and the right wing.
            g.FillRectangle(wall, mx - S(78), ground - S(58), S(190), S(58));
            g.FillPolygon(roof, new[] { new PointF(mx - S(86), ground - S(56)), new PointF(mx - S(34), ground - S(94)), new PointF(mx + S(18), ground - S(56)) });
            g.FillPolygon(roof, new[] { new PointF(mx + S(10), ground - S(56)), new PointF(mx + S(64), ground - S(86)), new PointF(mx + S(120), ground - S(56)) });
            g.FillRectangle(roof, mx + S(4), ground - S(62), S(14), S(8));
            for (float y = ground - S(52); y < ground; y += S(5)) g.DrawLine(trim, mx - S(78), y, mx + S(112), y);  // clapboard
            // The round turret at the front left, its cone and spike.
            using (var turret = new LinearGradientBrush(new RectangleF(mx - S(128), 0, S(48), 10), Hex("#56646F"), Hex("#2E3841"), LinearGradientMode.Horizontal))
                g.FillRectangle(turret, mx - S(128), ground - S(88), S(48), S(88));
            g.FillEllipse(roof, mx - S(132), ground - S(94), S(56), S(12));
            g.FillPolygon(roof, new[] { new PointF(mx - S(134), ground - S(88)), new PointF(mx - S(104), ground - S(132)), new PointF(mx - S(74), ground - S(88)) });
            using (var spike = new Pen(Hex("#1D232B"), S(2))) g.DrawLine(spike, mx - S(104), ground - S(132), mx - S(104), ground - S(142));
            for (float y = ground - S(84); y < ground; y += S(5)) g.DrawLine(trim, mx - S(128), y, mx - S(80), y);
            // The porch with its lit columns.
            using (var porch = new SolidBrush(Color.FromArgb(70, 190, 230, 210))) g.FillRectangle(porch, mx - S(80), ground - S(24), S(48), S(24));
            using (var column = new Pen(Hex("#A8BFC2"), S(2)))
                foreach (float x in new[] { mx - S(76), mx - S(60), mx - S(44) }) g.DrawLine(column, x, ground - S(26), x, ground);
            using (var porchRoof = new SolidBrush(Hex("#2A333D"))) g.FillRectangle(porchRoof, mx - S(84), ground - S(30), S(56), S(6));
            // Chimneys (smoke rises from these) and the windows (lit while the header animates).
            foreach (var (x, y) in new[] { (mx - S(10), ground - S(96)), (mx + S(92), ground - S(80)) })
            {
                g.FillRectangle(roof, x, y, S(8), S(16));
                chimneys.Add(new PointF(x + S(4), y));
            }
            foreach (var (x, y) in new[] { (mx - S(120), ground - S(70)), (mx - S(98), ground - S(70)), (mx - S(120), ground - S(46)), (mx - S(98), ground - S(46)),
                                           (mx - S(30), ground - S(46)), (mx - S(8), ground - S(46)), (mx + S(28), ground - S(46)), (mx + S(50), ground - S(46)),
                                           (mx + S(76), ground - S(46)), (mx + S(96), ground - S(46)), (mx + S(16), ground - S(96)), (mx + S(30), ground - S(96)),
                                           (mx + S(58), ground - S(70)), (mx - S(38), ground - S(74)) })
                windows.Add(new RectangleF(x, y, S(9), S(14)));

            // The gnarled tree at the right edge.
            using (var bark = new Pen(Hex("#0E1A17"), S(7)) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round })
            {
                float tx = W - S(60);
                g.DrawLines(bark, new[] { new PointF(tx, ground + S(4)), new PointF(tx - S(6), ground - S(44)), new PointF(tx + S(4), ground - S(78)) });
                bark.Width = S(4);
                g.DrawLines(bark, new[] { new PointF(tx - S(4), ground - S(46)), new PointF(tx - S(34), ground - S(70)), new PointF(tx - S(60), ground - S(74)) });
                g.DrawLines(bark, new[] { new PointF(tx + S(2), ground - S(62)), new PointF(tx + S(28), ground - S(96)), new PointF(tx + S(52), ground - S(104)) });
                bark.Width = S(2);
                g.DrawLine(bark, tx - S(34), ground - S(70), tx - S(42), ground - S(96));
                g.DrawLine(bark, tx + S(4), ground - S(78), tx - S(8), ground - S(112));
                g.DrawLine(bark, tx + S(28), ground - S(96), tx + S(30), ground - S(122));
                g.DrawLine(bark, tx - S(60), ground - S(74), tx - S(78), ground - S(66));
            }

            // The tiered fountain with the angel on top.
            float fx = W * 0.43f;
            using (var marble = new SolidBrush(Hex("#9CB6BC")))
            using (var marbleDark = new SolidBrush(Hex("#5D787E")))
            {
                g.FillPolygon(marbleDark, new[] { new PointF(fx - S(46), ground + S(8)), new PointF(fx - S(36), ground - S(4)), new PointF(fx + S(36), ground - S(4)), new PointF(fx + S(46), ground + S(8)) });
                g.FillEllipse(marbleDark, fx - S(44), ground - S(16), S(88), S(18));
                g.FillEllipse(marble, fx - S(44), ground - S(18), S(88), S(14));
                g.FillRectangle(marble, fx - S(4), ground - S(40), S(8), S(24));
                g.FillEllipse(marbleDark, fx - S(26), ground - S(42), S(52), S(11));
                g.FillEllipse(marble, fx - S(26), ground - S(44), S(52), S(9));
                g.FillRectangle(marble, fx - S(3), ground - S(56), S(6), S(13));
                // The angel: body, head and two raised wings.
                using var angel = new SolidBrush(Hex("#BCCCCE"));
                g.FillEllipse(angel, fx - S(5), ground - S(70), S(10), S(16));
                g.FillEllipse(angel, fx - S(4), ground - S(78), S(8), S(8));
                g.FillPolygon(angel, new[] { new PointF(fx - S(3), ground - S(66)), new PointF(fx - S(20), ground - S(80)), new PointF(fx - S(14), ground - S(64)) });
                g.FillPolygon(angel, new[] { new PointF(fx + S(3), ground - S(66)), new PointF(fx + S(20), ground - S(80)), new PointF(fx + S(14), ground - S(64)) });
            }
            fountainTop = new PointF(fx, ground - S(80));

            // The "Mystic Manor 1867" sign between two posts, and a swirl pad beside it.
            float sx = W * 0.565f, sy = ground - S(10);
            using (var post = new SolidBrush(Hex("#4A3220")))
            {
                g.FillRectangle(post, sx - S(44), sy - S(26), S(6), S(32));
                g.FillRectangle(post, sx + S(38), sy - S(26), S(6), S(32));
            }
            using (var board = new SolidBrush(Hex("#6E4C2D"))) g.FillRectangle(board, sx - S(40), sy - S(22), S(80), S(20));
            using (var boardEdge = new Pen(Hex("#3A2716"), S(1))) g.DrawRectangle(boardEdge, sx - S(40), sy - S(22), S(80), S(20));
            using (var signFont = new Font("Georgia", 7.5f, FontStyle.Bold))
            using (var carved = new SolidBrush(Hex("#E6D8B4")))
            {
                var fmt = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center };
                g.DrawString("Mystic Manor", signFont, carved, new RectangleF(sx - S(40), sy - S(22), S(80), S(20)), fmt);
            }
            DrawSwirlPad(g, W * 0.64f, ground + S(6), S(18), S(7), 0, Hex("#4F5A5F"));
        }
        coinSpots[0] = new PointF(W * 0.27f, ground + S(12));
        coinSpots[1] = new PointF(W * 0.505f, ground + S(4));
        coinSpots[2] = new PointF(W * 0.89f, ground + S(14));

        // The title like the game's logo: "SCOOBY-DOO!" in purple with an orange-tan rim, the rest in lavender.
        headerTitle?.Dispose();
        headerTitle = new Bitmap(size.Width, size.Height);
        using (var g = Graphics.FromImage(headerTitle))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAliasGridFit;
            var face = TitleFont();
            var style = (int)(face.IsStyleAvailable(FontStyle.Bold) ? FontStyle.Bold : FontStyle.Regular);
            float em = Math.Min(S(46), W * 0.045f), left = S(22);
            using (var path = new GraphicsPath())
            {
                path.AddString("SCOOBY-DOO!", face, style, em, new PointF(left, S(8)), StringFormat.GenericDefault);
                using (var outline = new Pen(Hex("#1A0F24"), S(9)) { LineJoin = LineJoin.Round }) g.DrawPath(outline, path);
                using (var rim = new Pen(Hex("#E8A04A"), S(4)) { LineJoin = LineJoin.Round }) g.DrawPath(rim, path);
                using var fill = new LinearGradientBrush(new RectangleF(0, S(10), 10, em), Hex("#A55FD0"), Hex("#5C2A8A"), LinearGradientMode.Vertical);
                g.FillPath(fill, path);
            }
            using (var path = new GraphicsPath())
            {
                path.AddString("Refrightened", face, style, em * 0.62f, new PointF(left + em * 0.5f, S(8) + em * 1.05f), StringFormat.GenericDefault);
                using (var outline = new Pen(Hex("#1A0F24"), S(6)) { LineJoin = LineJoin.Round }) g.DrawPath(outline, path);
                using var fill = new SolidBrush(Hex("#B7A3E6"));
                g.FillPath(fill, path);
            }
            using var credit = new Font("Segoe UI", 9.5f, FontStyle.Bold);
            using var shadow = new SolidBrush(Color.FromArgb(170, 0, 0, 0));
            using var light = new SolidBrush(Hex("#E3D8F5"));
            var at = new PointF(left + em * 0.52f, S(8) + em * 1.75f);
            g.DrawString("Made by JosiahG", credit, shadow, at.X + S(1), at.Y + S(1));
            g.DrawString("Made by JosiahG", credit, light, at);
        }
    }

    void PaintHeader(object? sender, PaintEventArgs e)
    {
        var g = e.Graphics;
        var r = ((Control)sender!).ClientRectangle;
        if (r.Width <= 0 || r.Height <= 0) return;
        if (headerBack == null || headerBack.Size != r.Size) BuildHeaderLayers(r.Size);
        double t = T;
        g.DrawImageUnscaled(headerBack!, 0, 0);
        g.SmoothingMode = SmoothingMode.AntiAlias;

        foreach (var (x, y, rad, phase) in stars)
        {
            int a = (int)(90 + 90 * Math.Sin(t * 2 + phase));
            using var b = new SolidBrush(Color.FromArgb(Math.Clamp(a, 0, 255), 235, 255, 235));
            g.FillEllipse(b, x - rad / 2, y - rad / 2, rad, rad);
        }
        // Green firework sparkles bursting over the grounds, as on the game's opening night.
        foreach (var (cx, cy, period, offset) in new[] { (0.86f, 44f, 4.6, 0.0), (0.62f, 30f, 6.1, 2.3), (0.98f, 70f, 5.3, 3.7) })
        {
            double p = ((t + offset) % period) / 1.6;
            if (p > 1) continue;
            float rad = (float)(Math.Sqrt(p) * S(34)), ox = r.Width * cx, oy = S((int)cy) + (float)(p * S(10));
            int alpha = (int)(230 * (1 - p));
            var sparkle = Color.FromArgb(alpha, 205, 250, 185);
            for (int i = 0; i < 16; i++)
            {
                double ang = i / 16.0 * Math.PI * 2 + cx;
                DrawSparkle(g, ox + (float)Math.Cos(ang) * rad, oy + (float)Math.Sin(ang) * rad, S(3), sparkle);
            }
        }
        // Pale smoke rising from the chimneys.
        foreach (var c in chimneys)
            for (int i = 0; i < 9; i++)
            {
                float rise = i * S(9), w = S(7) + i * 1.6f * k;
                float drift = (float)(Math.Sin(t * 1.3 + i * 0.7 + c.X) * S(3) + i * S(1));
                int a = 120 - i * 12;
                using var smoke = new SolidBrush(Color.FromArgb(Math.Max(a, 0), 236, 244, 236));
                g.FillEllipse(smoke, c.X - w / 2 + drift, c.Y - rise - S(10), w, S(12));
            }

        g.DrawImageUnscaled(headerFront!, 0, 0);
        // Amber arched windows, steady with a slow candle flicker.
        for (int i = 0; i < windows.Count; i++)
        {
            var w = windows[i];
            int a = (int)(205 + 40 * Math.Sin(t * 2.2 + i * 1.3));
            using var lit = new SolidBrush(Color.FromArgb(Math.Clamp(a, 0, 255), 242, 170, 64));
            g.FillRectangle(lit, w.X, w.Y + w.Width / 2, w.Width, w.Height - w.Width / 2);
            g.FillPie(lit, w.X, w.Y, w.Width, w.Width, 180, 180);
            using var bar = new Pen(Color.FromArgb(140, 60, 40, 20), 1);
            g.DrawLine(bar, w.X + w.Width / 2, w.Y + S(2), w.X + w.Width / 2, w.Bottom);
        }
        // The fountain's spray: drops arcing out and falling back into the basin.
        using (var drop = new SolidBrush(Color.FromArgb(170, 214, 238, 246)))
            for (int i = 0; i < 18; i++)
            {
                double p = (t * 0.9 + i / 18.0) % 1.0, side = i % 2 == 0 ? 1 : -1, spread = 0.5 + (i % 5) * 0.12;
                float x = fountainTop.X + (float)(side * p * S(26) * spread);
                float y = fountainTop.Y + S(8) - (float)(Math.Sin(p * Math.PI) * S(16)) + (float)(p * p * S(30));
                g.FillEllipse(drop, x - S(1), y - S(1), 2.4f * k, 2.4f * k);
            }
        // Scooby Snack S-coins hover and turn; click one to grab it (it flies up and comes back later).
        for (int i = 0; i < coinSpots.Length; i++)
        {
            float w = S(20), x = coinSpots[i].X, y = coinSpots[i].Y + (float)(Math.Sin(t * 2.4 + i * 2) * S(4));
            float spin = (float)Math.Abs(Math.Cos(t * 1.6 + i * 1.9));
            double got = Progress("coin" + i, 1.2);
            int alpha = 255;
            if (got >= 0)
            {
                y -= (float)(got * S(60));
                alpha = (int)(255 * (1 - got));
                for (int q = 0; q < 4; q++)
                    DrawSparkle(g, x + (float)Math.Cos(q * 1.57 + got * 6) * S(16), y + (float)Math.Sin(q * 1.57 + got * 6) * S(16), S(4), Color.FromArgb(alpha, Gold));
            }
            coinRects[i] = got >= 0 ? Rectangle.Empty : new Rectangle((int)(x - w * 0.8f), (int)(y - w * 0.8f), (int)(w * 1.6f), (int)(w * 1.6f));
            using (var shade = new SolidBrush(Color.FromArgb(alpha / 4, 0, 0, 0))) g.FillEllipse(shade, x - w * 0.4f, coinSpots[i].Y + S(10), w * 0.8f, S(4));
            DrawCoin(g, x, y, w, Math.Max(0.15f, spin), alpha);
        }
        g.DrawImageUnscaled(headerTitle!, 0, 0);
    }

    // Scooby's picture (embedded scooby.png), resized once per size and kept.
    static readonly Image? ScoobyArt = LoadArt("scooby.png");
    readonly Dictionary<int, Bitmap> scoobySized = new();

    static Image? LoadArt(string name)
    {
        using var s = typeof(MainForm).Assembly.GetManifestResourceStream("ScoobyReMasked." + name);
        return s == null ? null : Image.FromStream(new MemoryStream(ReadAll(s)));
    }

    static byte[] ReadAll(Stream s) { using var m = new MemoryStream(); s.CopyTo(m); return m.ToArray(); }

    static Bitmap SizedArt(Image art, int height)
    {
        var b = new Bitmap(Math.Max(1, art.Width * height / art.Height), Math.Max(1, height));
        using var g = Graphics.FromImage(b);
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        g.DrawImage(art, new Rectangle(Point.Empty, b.Size));
        return b;
    }

    // Scooby stands on a swirl pad under the menu; click him and he warps away and back, like at the game's
    // checkpoints. The S-coins grabbed up top are counted here.
    void PaintNav(object? sender, PaintEventArgs e)
    {
        var nav = (Control)sender!;
        var g = e.Graphics;
        double t = T;
        navSpriteTop = pages.Count > 0 ? pages[^1].button.Bottom + S(10) : 0;
        int bottom = nav.ClientSize.Height - S(10);
        int room = bottom - navSpriteTop - S(60);
        if (room < S(80) || ScoobyArt == null) { scoobyRect = Rectangle.Empty; return; }
        int height = Math.Min(S(180), room);
        if (!scoobySized.TryGetValue(height, out var art)) scoobySized[height] = art = SizedArt(ScoobyArt, height);
        int cx = (nav.Width + S(16)) / 2;
        float padY = bottom - S(30);
        double warp = Progress("warp", 1.6);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        var glow = warp >= 0 ? Color.FromArgb(255, 160, 110, 230) : Hex("#4F5A5F");
        DrawSwirlPad(g, cx, padY, S(62), S(16), warp >= 0 ? t * 9 : t * 0.6, glow);
        // Warp: shrink into the pad (0..0.4), gone (0.4..0.6), grow back out (0.6..1).
        float scale = warp < 0 ? 1 : warp < 0.4 ? (float)(1 - warp / 0.4) : warp < 0.6 ? 0 : (float)((warp - 0.6) / 0.4);
        int lift = (int)(Math.Sin(t * 1.8) * S(2));
        var face = new Rectangle(cx - art.Width / 2, (int)padY - art.Height + S(4) - lift, art.Width, art.Height);
        scoobyRect = face;
        if (scale > 0.02f)
        {
            int w = (int)(art.Width * scale), h = (int)(art.Height * scale);
            g.DrawImage(art, new Rectangle(cx - w / 2, face.Bottom - h, w, h));
        }
        if (warp >= 0 && warp < 0.8)
            for (int q = 0; q < 6; q++)
            {
                double a = q / 6.0 * Math.PI * 2 + t * 8;
                DrawSparkle(g, cx + (float)Math.Cos(a) * S(40), padY - S(30) - (float)(warp * S(60)) + (float)Math.Sin(a) * S(10), S(5), Color.FromArgb(220, 200, 170, 255));
            }
        using var f = new Font("Segoe UI", 9.5f, FontStyle.Bold);
        using var text = new SolidBrush(Ink);
        var fmt = new StringFormat { Alignment = StringAlignment.Center };
        g.DrawString(snacks == 0 ? "Grab the S-coins up top!" : $"Scooby Snacks: {snacks}", f, text, cx, bottom - S(12), fmt);
    }

    // ----- Shared pieces -----
    // A white card holding one page's controls, top to bottom.
    static (Panel card, FlowLayoutPanel body) NewCard(string heading)
    {
        var card = new BufferedPanel { Padding = S(22, 16, 22, 16) };
        card.Paint += (sender, e) =>
        {
            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            var r = ((Control)sender!).ClientRectangle;
            r.Width -= S(8); r.Height -= S(8);
            r.Offset(S(2), S(2));
            using var path = Rounded(r, S(14));
            using var shadow = Rounded(new Rectangle(r.X + S(5), r.Y + S(5), r.Width, r.Height), S(14));
            using (var shade = new SolidBrush(Color.FromArgb(50, 0, 0, 0))) g.FillPath(shade, shadow);
            using (var paper = new SolidBrush(Paper)) g.FillPath(paper, path);
            using (var border = new Pen(Ink, S(3))) g.DrawPath(border, path);
        };
        var body = new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, FlowDirection = FlowDirection.TopDown, WrapContents = false, BackColor = Paper };
        card.AutoScroll = true;
        body.Controls.Add(new Label { Text = heading, Font = new Font("Segoe UI", 18f, FontStyle.Bold), ForeColor = Ink, AutoSize = true, Margin = S(0, 0, 0, 10) });
        card.Controls.Add(body);
        return (card, body);
    }

    static GraphicsPath Rounded(Rectangle r, int radius)
    {
        var p = new GraphicsPath();
        int d = Math.Max(2, radius * 2);
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    static Label Note(string text, int width = 680) => new()
    {
        Text = text, AutoSize = true, MaximumSize = new Size(S(width), 0), ForeColor = Ink, Margin = S(0, 6, 0, 6),
    };

    static Button Btn(string text, EventHandler onClick, Color? back = null)
    {
        var b = new Button
        {
            Text = text, AutoSize = true, FlatStyle = FlatStyle.Flat, BackColor = back ?? Gold, ForeColor = Ink,
            Font = new Font("Segoe UI", 10.5f, FontStyle.Bold), Padding = S(10, 4, 10, 4), Margin = S(0, 6, 10, 6), Cursor = glassHand,
        };
        b.FlatAppearance.BorderColor = Ink;
        b.FlatAppearance.BorderSize = S(2);
        b.Click += onClick;
        return b;
    }

    // ----- Play -----
    Control BuildPlayPage()
    {
        var (card, body) = NewCard("Ready, gang?");
        playButton = Btn("PLAY", (_, _) => Launch(), Orange);
        playButton.Font = new Font("Segoe UI", 24f, FontStyle.Bold);
        playButton.Padding = S(60, 8, 60, 8);
        body.Controls.Add(playButton);
        playStatus = Note("");
        playStatus.Font = new Font("Segoe UI", 10.5f, FontStyle.Bold);
        body.Controls.Add(playStatus);
        chooseDisc = Btn("Choose disc image (.iso, .gcm, .ciso)...", async (_, _) => await ChooseDisc(), Paper);
        body.Controls.Add(chooseDisc);
        progress = new ProgressBar { Width = S(520), Height = S(16), Visible = false, Margin = S(0, 4, 0, 6) };
        body.Controls.Add(progress);
        body.Controls.Add(dumpHelp = Note(
            "Scooby-Doo: Refrightened runs your own copy of Scooby-Doo! Night of 100 Frights for the GameCube (USA, GIHE78, version 1.01). " +
            "Dump the disc you own (for example with CleanRip on a Wii) as a plain .iso or .ciso, then choose it above. " +
            "The launcher copies the game files into the Disc folder once; the image file isn't needed afterwards."));
        body.Controls.Add(Note("In the game, F10 opens the settings menu (resolution, picture shape, controls, audio) and F11 switches between fullscreen and a window."));
        // Scooby's tips: click the bubble for another one.
        var tipRow = new FlowLayoutPanel { AutoSize = true, Margin = S(0, 10, 0, 6) };
        if (ScoobyArt != null)
        {
            var pic = SizedArt(ScoobyArt, S(60));
            tipRow.Controls.Add(new PictureBox { Image = pic, Size = pic.Size, Margin = S(0, 0, 8, 0) });
        }
        tipLabel = new Label
        {
            AutoSize = true, MaximumSize = new Size(S(600), 0), BackColor = TealLight, ForeColor = Ink,
            BorderStyle = BorderStyle.FixedSingle, Padding = S(10, 8, 10, 8), Cursor = glassHand, Margin = S(0, 4, 0, 0),
        };
        tipLabel.Click += (_, _) => NextTip();
        tipRow.Controls.Add(tipLabel);
        tipIndex = Random.Shared.Next(Tips.Length) - 1;
        NextTip();
        body.Controls.Add(tipRow);
        var row = new FlowLayoutPanel { AutoSize = true, Margin = Padding.Empty };
        row.Controls.Add(Btn("Open game folder", (_, _) => Process.Start("explorer.exe", play), Paper));
        row.Controls.Add(Btn("Open saves and settings", (_, _) => Process.Start("explorer.exe", Directory.CreateDirectory(userData).FullName), Paper));
        body.Controls.Add(row);
        return card;
    }

    static readonly string[] Tips =
    {
        "Press F10 in the game to change resolution, picture shape or controls without quitting.",
        "F11 flips the game between fullscreen and a window.",
        "Cinematic 2.39:1 shows far more of Mystic Manor than the GameCube ever could.",
        "Any gamepad works as a GameCube controller right away.",
        "Got an HDR screen? Switch HDR on in Windows, then on the Display page.",
        "Saves live in data\\UserData. A backup now and then never hurts.",
        "Grab the floating S-coins in the header. Scooby counts every one.",
        "Click Scooby to warp him on the swirl pad, just like the checkpoints in Mystic Manor.",
        "Scooby's on his own this time. Like, good luck, Scoob!",
    };
    Label? tipLabel;
    int tipIndex;

    void NextTip()
    {
        tipIndex = (tipIndex + 1) % Tips.Length;
        if (tipLabel != null) tipLabel.Text = "Scooby says: " + Tips[tipIndex];
    }

    (bool ok, string text) DiscState()
    {
        var boot = Path.Combine(discDir, "sys", "boot.bin");
        if (!File.Exists(boot)) return (false, "No game disc set up yet. Choose your Scooby-Doo! Night of 100 Frights disc image below.");
        var id = System.Text.Encoding.ASCII.GetString(File.ReadAllBytes(boot), 0, 6);
        return id == GcDisc.WantedId ? (true, "Scooby-Doo! Night of 100 Frights (GIHE78) is ready. Zoinks, let's go!") : (false, $"The Disc folder holds {id}, not Scooby-Doo! Night of 100 Frights USA (GIHE78).");
    }

    void RefreshDisc()
    {
        if (playStatus == null) return;
        var (ok, text) = DiscState();
        playStatus.Text = text;
        playStatus.ForeColor = ok ? Hex("#1E7F55") : Hex("#B4561A");
        playButton.Enabled = ok && File.Exists(Path.Combine(play, GameExe));
        if (!playButton.Enabled) playButton.BackColor = Hex("#D8CFC0");
        chooseDisc.Text = ok ? "Change disc image..." : "Choose disc image (.iso, .gcm, .ciso)...";
        dumpHelp.Visible = !ok;
    }

    async Task ChooseDisc()
    {
        using var dialog = new OpenFileDialog
        {
            Title = "Choose your Scooby-Doo! Night of 100 Frights disc image",
            Filter = "GameCube disc images (*.iso;*.gcm;*.ciso)|*.iso;*.gcm;*.ciso|All files (*.*)|*.*",
        };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        GcDisc disc;
        try { disc = GcDisc.Open(dialog.FileName); }
        catch (Exception e) { MessageBox.Show(this, "That file can't be read: " + e.Message, AppTitle); return; }
        using (disc)
        {
            var problem = disc.Problem();
            if (problem.Length > 0) { MessageBox.Show(this, problem, AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
            var staging = discDir + ".new";
            if (Directory.Exists(staging)) Directory.Delete(staging, true);
            chooseDisc.Enabled = playButton.Enabled = false;
            progress.Visible = true; progress.Value = 0;
            var report = new Progress<(int done, int total, string name)>(p =>
            {
                progress.Maximum = Math.Max(1, p.total); progress.Value = Math.Min(p.done, progress.Maximum);
                playStatus.Text = $"Extracting {p.done}/{p.total}: {p.name}";
            });
            try
            {
                await Task.Run(() => disc.Extract(staging, (d, t, n) => ((IProgress<(int, int, string)>)report).Report((d, t, n))));
                if (Directory.Exists(discDir)) Directory.Delete(discDir, true);
                Directory.Move(staging, discDir);
                var cfg = new GameConfig(configPath);
                cfg.Set("paths", "dvd_root", IsRelease ? "'../Disc/DATA'" : "'../../Disc/DATA'");  // relative to UserData, so the folder can move
                cfg.Save();
            }
            catch (Exception e) { MessageBox.Show(this, "Extraction failed: " + e.Message, AppTitle, MessageBoxButtons.OK, MessageBoxIcon.Error); }
            finally { progress.Visible = false; chooseDisc.Enabled = true; RefreshDisc(); }
        }
    }

    void Launch()
    {
        var exe = Path.Combine(play, GameExe);
        if (!File.Exists(exe)) { MessageBox.Show(this, "The game files (the data folder) are missing. Re-extract the download next to this launcher.", AppTitle); return; }
        Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = play, UseShellExecute = true });
        WindowState = FormWindowState.Minimized;
    }

    // ----- Display -----
    Control BuildDisplayPage()
    {
        var (card, body) = NewCard("Display");
        var cfg = new GameConfig(configPath);
        var table = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, BackColor = Paper, Margin = S(0, 4, 0, 8) };
        void Row(string label, string key, (string text, string raw)[] options, string fallback)
        {
            var box = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = S(360), Cursor = glassHand };
            foreach (var o in options) box.Items.Add(o.text);
            var current = cfg.Get("video", key) ?? fallback;
            int index = Array.FindIndex(options, o => o.raw.Trim('"') == current.Trim('"'));
            box.SelectedIndex = index >= 0 ? index : Array.FindIndex(options, o => o.raw.Trim('"') == fallback);
            box.SelectedIndexChanged += (_, _) =>
            {
                var c = new GameConfig(configPath);
                c.Set("video", key, options[box.SelectedIndex].raw);
                c.Save();
            };
            table.Controls.Add(new Label { Text = label, AutoSize = true, ForeColor = Ink, Font = new Font("Segoe UI", 10.5f, FontStyle.Bold), Margin = S(0, 10, 16, 8) });
            table.Controls.Add(box);
        }
        Row("Window", "display_mode", new[] { ("Borderless fullscreen", "\"borderless\""), ("Window", "\"windowed\""), ("Exclusive fullscreen", "\"exclusive\"") }, "borderless");
        Row("Resolution", "resolution_multiplier", new[] { ("720p", "1.5"), ("1080p", "2.25"), ("4K", "4.5"), ("Your screen's size", "0") }, "2.25");
        Row("Picture shape", "aspect_mode", new[] { ("Original 4:3", "0"), ("Widescreen 16:9", "1"), ("Fill the screen", "2"), ("Cinematic 2.39:1", "3") }, "3");
        Row("Frame rate", "frame_interpolation_fps", new[] { ("30 fps (original)", "0") }, "0");  // the game runs at 30 fps; smoothing is built for 60 fps games
        Row("HDR", "hdr", new[] { ("Off", "false"), ("On (needs HDR on in Windows display settings)", "true") }, "false");
        Row("HDR brightness", "hdr_paper_white_nits", new[] { ("Dim (120 nits)", "120.0"), ("Normal (200 nits)", "200.0"), ("Bright (300 nits)", "300.0"), ("Brightest (400 nits)", "400.0") }, "200.0");
        Row("HDR highlights", "hdr_peak_nits", new[] { ("Subtle (400 nits)", "400.0"), ("Standard (1000 nits)", "1000.0"), ("Strong (1500 nits)", "1500.0") }, "1000.0");
        body.Controls.Add(table);
        body.Controls.Add(Note("Changes are saved at once and apply the next time the game starts. In the game, F10 opens the same " +
                               "settings and F11 switches between fullscreen and a window."));
        return card;
    }

    // ----- Controls -----
    Control BuildControlsPage()
    {
        var (card, body) = NewCard("Controls");
        body.Controls.Add(Note("Gamepads (Xbox, PlayStation, Switch Pro, GameCube adapter...) work right away as a GameCube controller. " +
                               "To change any button, press F10 in the game and open Controller settings."));
        body.Controls.Add(new Label { Text = "Keyboard", Font = new Font("Segoe UI", 13f, FontStyle.Bold), ForeColor = Ink, AutoSize = true, Margin = S(0, 10, 0, 0) });
        var table = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, BackColor = Paper, Margin = S(0, 8, 0, 8), CellBorderStyle = TableLayoutPanelCellBorderStyle.Single };
        foreach (var (what, key) in new[] { ("Move", "W A S D"), ("Camera (C-stick)", "Arrow keys"), ("A (jump)", "Space"), ("B", "Left Shift"),
                     ("X / Y", "R / F"), ("Z", "C"), ("L / R", "Q / E"), ("Start (pause)", "Enter"), ("D-pad", "I J K L") })
        {
            table.Controls.Add(new Label { Text = what, AutoSize = true, ForeColor = Ink, Margin = S(8, 6, 24, 6) });
            table.Controls.Add(new Label { Text = key, AutoSize = true, ForeColor = Ink, Font = new Font("Segoe UI", 10.5f, FontStyle.Bold), Margin = S(8, 6, 24, 6) });
        }
        body.Controls.Add(table);
        return card;
    }

    // ----- Mods -----
    Control BuildModsPage()
    {
        var (card, body) = NewCard("Mods");
        body.Controls.Add(Note("A mod is a folder in data\\UserData\\mods. Its files\\ folder mirrors the disc's files\\ (replacing game files), " +
                               "and its textures\\ folder holds texture replacements. Untick a mod to switch it off; when two mods change the same file, the later name wins."));
        var list = new CheckedListBox { Width = S(520), Height = S(220), CheckOnClick = true, BorderStyle = BorderStyle.FixedSingle, Margin = S(0, 8, 0, 8) };
        void Fill()
        {
            list.Items.Clear();
            if (!Directory.Exists(modsDir)) return;
            foreach (var d in Directory.GetDirectories(modsDir).OrderBy(d => d, StringComparer.OrdinalIgnoreCase))
                list.Items.Add(Path.GetFileName(d), !File.Exists(Path.Combine(d, "disabled")));
        }
        list.ItemCheck += (_, e) =>
        {
            var flag = Path.Combine(modsDir, (string)list.Items[e.Index], "disabled");
            if (e.NewValue == CheckState.Checked) File.Delete(flag); else File.WriteAllText(flag, "");
        };
        body.Controls.Add(list);
        var row = new FlowLayoutPanel { AutoSize = true, Margin = Padding.Empty };
        row.Controls.Add(Btn("Open the mods folder", (_, _) => Process.Start("explorer.exe", Directory.CreateDirectory(modsDir).FullName), Paper));
        row.Controls.Add(Btn("Refresh", (_, _) => Fill(), Paper));
        body.Controls.Add(row);
        Fill();
        return card;
    }
}

sealed class BufferedPanel : Panel
{
    public BufferedPanel() { DoubleBuffered = true; ResizeRedraw = true; }
}

sealed class BufferedFlow : FlowLayoutPanel
{
    public BufferedFlow() { DoubleBuffered = true; ResizeRedraw = true; }
}
