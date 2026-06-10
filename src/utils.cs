using System;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Runtime.InteropServices;
using System.Xml;
namespace UnpackKindleS
{

    class Util
    {

        public static byte[] SubArray(byte[] src, ulong start, ulong length)
        {
            byte[] r = new byte[length];
            for (ulong i = 0; i < length; i++) { r[i] = src[start + i]; }
            return r;
        }
        public static byte[] SubArray(byte[] src, int start, int length)
        {
            byte[] r = new byte[length];
            for (int i = 0; i < length; i++) { r[i] = src[start + i]; }
            return r;
        }
        public static string ToHexString(byte[] src, uint start, uint length)
        {
            //https://stackoverflow.com/a/14333437/48700
            char[] c = new char[length * 2];
            int b;
            for (int i = 0; i < length; i++)
            {
                b = src[start + i] >> 4;
                c[i * 2] = (char)(55 + b + (((b - 10) >> 31) & -7));
                b = src[start + i] & 0xF;
                c[i * 2 + 1] = (char)(55 + b + (((b - 10) >> 31) & -7));
            }
            return new string(c);
        }
        public static UInt64 GetUInt64(byte[] src, ulong start)
        {
            byte[] t = SubArray(src, start, 8);
            Array.Reverse(t);
            return BitConverter.ToUInt64(t);
        }
        //big edian handle:
        public static UInt32 GetUInt32(byte[] src, ulong start)
        {
            byte[] t = SubArray(src, start, 4);
            Array.Reverse(t);
            return BitConverter.ToUInt32(t);
        }
        public static UInt16 GetUInt16(byte[] src, ulong start)
        {
            byte[] t = SubArray(src, start, 2);
            Array.Reverse(t);
            return BitConverter.ToUInt16(t);
        }
        public static byte GetUInt8(byte[] src, ulong start)
        {
            return src[start];
        }

        public static string GuessImageType(byte[] data)
        {
            if (data.Length < 4) return null;
            if (data[0] == 0xff && data[1] == 0xd8
            // && data[data.Length - 2] == 0xff && data[data.Length - 1] == 0xd9//有的会在后面跟几个0字节
            )
                return ".jpg";
            if (Encoding.ASCII.GetString(data, 0, 4) == "GIF8")
                return ".gif";
            if (Encoding.ASCII.GetString(data, 0, 4) == "\x89\x50\x4e\x47")
                return ".png";

            return null;
        }

        public static string GetOuterXML(string data, string tagname)
        {
            int start = data.IndexOf("<" + tagname); if (start < 0) return null;
            int end = data.IndexOf("</" + tagname + ">") + 3 + tagname.Length;
            return data.Substring(start, end - start);
        }
        public static string GetInnerXML(XmlElement e)
        {
            string r = "";
            if (e.ChildNodes == null) return e.InnerXml;
            foreach (XmlNode n in e.ChildNodes)
            {

                if (n.NodeType == XmlNodeType.Element)
                {
                    r += "    " + GetOuterXML((XmlElement)n).Replace("\n", "    \n") + "\n";
                    continue;
                }
                if (n.NodeType == XmlNodeType.Text)
                {
                    r += n.OuterXml;
                }
            }
            return r;
        }
        public static string GetOuterXML(XmlElement e)
        {
            string inner = GetInnerXML(e);
            string attr = "";
            if (e.Attributes != null)
                foreach (XmlAttribute a in e.Attributes)
                {
                    attr += string.Format(" {0}=\"{1}\"", a.Name, a.Value);
                }
            if (inner == "")
            {
                return string.Format("<{0}{1} />", e.Name, attr);
            }
            return String.Format("<{0}{2}>{1}</{0}>", e.Name, inner, attr);
        }


        public static T GetStructBE<T>(byte[] data, int offset)
        {
            int size = Marshal.SizeOf(typeof(T));
            Byte[] data_trimed = SubArray(data, offset, size);
            Array.Reverse(data_trimed);
            IntPtr structPtr = Marshal.AllocHGlobal(size);
            Marshal.Copy(data_trimed, 0, structPtr, size);
            T r = (T)Marshal.PtrToStructure(structPtr, typeof(T));
            Marshal.FreeHGlobal(structPtr);
            return r;
        }

        public static UInt64 DecodeBase32(string s)
        {
            UInt64 r = 0;
            foreach (char c in s)
            {
                uint v;
                if (char.IsDigit(c))
                {
                    v = (uint)c - (uint)'0';
                }
                else
                {
                    v = (uint)c - (uint)'A' + 10;
                }
                r = (r * 32) + v;

            }
            return r;
        }
        public static string Number(int number, int length = 4)
        {
            string r = number.ToString();
            for (int j = length - r.Length; j > 0; j--) r = "0" + r;
            return r;
        }

        public static string XmlEscape(string s)
        {
            if (s == null) return "";
            return System.Security.SecurityElement.Escape(s);
        }

        public static string FilenameCheck(string s)
        {
            return s
            .Replace('?', '？')
            .Replace('\\', '＼')
            .Replace('/', '／')
            .Replace(':', '：')
            .Replace('*', '＊')
            .Replace('"', '＂')
            .Replace('|', '｜')
            .Replace('<', '＜')
            .Replace('>', '＞')
            ;
        }

        public static (int, int) GetImageSize(byte[] data)
        {
            // JPEG: scan for SOF marker (FF C0-CF, excluding C4/C8/CC)
            if (data.Length > 3 && data[0] == 0xFF && data[1] == 0xD8)
            {
                int i = 2;
                while (i + 8 < data.Length)
                {
                    if (data[i] != 0xFF) break;
                    byte marker = data[i + 1];
                    int segLen = (data[i + 2] << 8) | data[i + 3];
                    if (marker >= 0xC0 && marker <= 0xCF
                        && marker != 0xC4 && marker != 0xC8 && marker != 0xCC)
                    {
                        int h = (data[i + 5] << 8) | data[i + 6];
                        int w = (data[i + 7] << 8) | data[i + 8];
                        return (w, h);
                    }
                    i += 2 + segLen;
                }
            }
            // PNG: IHDR dimensions at offset 16 (big-endian)
            if (data.Length >= 24
                && data[0] == 0x89 && data[1] == 0x50 && data[2] == 0x4E && data[3] == 0x47)
            {
                int w = (data[16] << 24) | (data[17] << 16) | (data[18] << 8) | data[19];
                int h = (data[20] << 24) | (data[21] << 16) | (data[22] << 8) | data[23];
                return (w, h);
            }
            // GIF: logical screen descriptor at offset 6 (little-endian)
            if (data.Length >= 10
                && data[0] == 0x47 && data[1] == 0x49 && data[2] == 0x46)
            {
                int w = data[6] | (data[7] << 8);
                int h = data[8] | (data[9] << 8);
                return (w, h);
            }
            return (0, 0);
        }
    }

    [System.Serializable]
    public class UnpackKindleSException : System.Exception
    {
        public UnpackKindleSException(string message) : base(message) { }
        protected UnpackKindleSException(
            System.Runtime.Serialization.SerializationInfo info,
            System.Runtime.Serialization.StreamingContext context) : base(info, context) { }
    }
}