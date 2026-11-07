using System;
using System.Drawing;
using System.IO;
using System.Media;
using System.Runtime.InteropServices;
using System.Windows.Forms;

static class UiFixture
{
    [DllImport("user32.dll")]
    static extern bool AllowSetForegroundWindow(int processId);

    [STAThread]
    static void Main(string[] launchArgs)
    {
        Application.EnableVisualStyles();
        using (var form = new Form())
        using (var secondary = new Form())
        using (var timer = new Timer())
        using (var audio = new SoundPlayer(SilentWave()))
        {
            form.Text = "ComputerFlow 003 UI Test";
            form.ClientSize = new Size(565, 310);
            form.StartPosition = FormStartPosition.CenterScreen;
            var edit = new TextBox();
            edit.SetBounds(28, 25, 450, 32);
            var toggle = new CheckBox { Text = "Test Option" };
            toggle.SetBounds(28, 85, 220, 32);
            var button = new Button { Text = "Test Button" };
            button.SetBounds(28, 130, 140, 36);
            button.Click += (sender, args) => button.Text = "Button Used";
            var canvas = new PictureBox { BackColor = Color.RoyalBlue };
            canvas.SetBounds(28, 190, 230, 65);
            canvas.Paint += (sender, args) => args.Graphics.DrawString(
                "VISUAL TARGET", form.Font, Brushes.White, 30, 25);
            canvas.Click += (sender, args) => canvas.BackColor =
                canvas.BackColor == Color.RoyalBlue ? Color.DarkOrange : Color.RoyalBlue;
            form.Controls.AddRange(new Control[] { edit, toggle, button, canvas });
            secondary.Text = "ComputerFlow 003 Secondary";
            secondary.StartPosition = FormStartPosition.CenterScreen;
            var secondEdit = new TextBox();
            secondEdit.SetBounds(12, 12, 200, 25);
            var tabs = new TabControl();
            tabs.SetBounds(12, 50, 240, 130);
            tabs.TabPages.Add("Startseite");
            tabs.TabPages.Add("Pruefseite");
            secondary.Controls.Add(secondEdit);
            secondary.Controls.Add(tabs);
            timer.Interval = 90000;
            timer.Tick += (sender, args) => form.Close();
            form.Shown += (sender, args) =>
            {
                secondary.Show();
                secondEdit.Focus();
                secondary.WindowState = FormWindowState.Minimized;
                form.Activate();
                edit.Focus();
                int client;
                if (launchArgs.Length > 0 && Int32.TryParse(launchArgs[0], out client))
                    AllowSetForegroundWindow(client);
                audio.PlayLooping();
                Console.WriteLine(form.Handle.ToInt64() + " " + canvas.Handle.ToInt64());
                Console.Out.Flush();
                timer.Start();
            };
            Application.Run(form);
        }
    }

    static Stream SilentWave()
    {
        var data = new MemoryStream();
        var wav = new BinaryWriter(data);
        const int length = 32000;
        wav.Write(new[] { 'R', 'I', 'F', 'F' }); wav.Write(36 + length);
        wav.Write(new[] { 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ' }); wav.Write(16);
        wav.Write((short)1); wav.Write((short)1); wav.Write(16000); wav.Write(32000);
        wav.Write((short)2); wav.Write((short)16);
        wav.Write(new[] { 'd', 'a', 't', 'a' }); wav.Write(length); wav.Write(new byte[length]);
        data.Position = 0;
        return data;
    }
}
