import struct
import argparse
from PIL import Image

# Glyph 정보를 담을 클래스
class Glyph:
    def __init__(self, id_, x, y, width, height, xoffset, yoffset, xadvance, page, chnl):
        self.id = id_
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.xoffset = xoffset
        self.yoffset = yoffset
        self.xadvance = xadvance
        self.page = page
        self.chnl = chnl

    def __repr__(self):
        return f'Glyph(id={self.id}, x={self.x}, y={self.y}, w={self.width}, h={self.height}, ' \
               f'xoff={self.xoffset}, yoff={self.yoffset}, xadv={self.xadvance}, page={self.page})'

# BMFont 파서를 위한 클래스
class BMFont:
    def __init__(self):
        self.info = {}
        self.common = {}
        self.pages = []      # 페이지 파일명 리스트 (보통 하나 이상의 PNG)
        self.glyphs = {}     # 문자 코드 -> Glyph 객체 매핑
        self.kernings = {}   # (first, second) -> amount

    def load(self, fnt_path):
        with open(fnt_path, 'rb') as f:
            # 헤더: "BMF" + 버전(1바이트)
            header = f.read(3)
            if header != b'BMF':
                raise ValueError("파일 헤더가 'BMF'가 아닙니다.")
            version = struct.unpack("B", f.read(1))[0]
            if version != 3:
                raise ValueError("버전 3의 BMFont만 지원합니다. (현재 버전: {})".format(version))

            # 파일 끝까지 블록을 읽습니다.
            while True:
                block_header = f.read(5)
                if not block_header or len(block_header) < 5:
                    break
                block_id = block_header[0]
                block_size = struct.unpack("<I", block_header[1:])[0]
                block_data = f.read(block_size)
                if block_id == 1:
                    self._parse_info_block(block_data)
                elif block_id == 2:
                    self._parse_common_block(block_data)
                elif block_id == 3:
                    self._parse_pages_block(block_data)
                elif block_id == 4:
                    self._parse_chars_block(block_data)
                elif block_id == 5:
                    self._parse_kernings_block(block_data)
                else:
                    # 알 수 없는 블록은 무시
                    pass

    def _parse_info_block(self, data):
        # info 블록의 기본 정보 (필요한 정보만 파싱)
        # fontSize (int16), bitField(1B), charSet(1B), stretchH(uint16), aa(1B),
        # padding (4B), spacing (2B), outline(1B) + null-terminated font name
        fmt = "<hBBHB4B2BB"
        fixed_size = struct.calcsize(fmt)
        unpacked = struct.unpack(fmt, data[:fixed_size])
        self.info['fontSize'] = unpacked[0]
        self.info['bitField'] = unpacked[1]
        self.info['charSet'] = unpacked[2]
        self.info['stretchH'] = unpacked[3]
        self.info['aa'] = unpacked[4]
        self.info['padding'] = unpacked[5:9]
        self.info['spacing'] = unpacked[9:11]
        self.info['outline'] = unpacked[11]
        # 나머지는 null-terminated string
        font_name = data[fixed_size:].split(b'\0', 1)[0].decode('utf-8')
        self.info['fontName'] = font_name

    def _parse_common_block(self, data):
        # common 블록: lineHeight, base, scaleW, scaleH, pages, bitField, alphaChnl, redChnl, greenChnl, blueChnl
        fmt = "<HHHHHBBBB"
        unpacked = struct.unpack(fmt, data[:struct.calcsize(fmt)])
        keys = ['lineHeight', 'base', 'scaleW', 'scaleH', 'pages', 'bitField',
                'alphaChnl', 'redChnl', 'greenChnl', 'blueChnl']
        self.common = dict(zip(keys, unpacked))

    def _parse_pages_block(self, data):
        # 페이지 블록: null-terminated 문자열들이 연달아 있음. common['pages'] 개수만큼 읽음.
        pages = []
        remaining = data
        for _ in range(self.common.get('pages', 1)):
            # null 문자 전까지 읽음
            if b'\0' in remaining:
                page_name, remaining = remaining.split(b'\0', 1)
                pages.append(page_name.decode('utf-8'))
            else:
                break
        self.pages = pages

    def _parse_chars_block(self, data):
        # 각 글리프 정보는 20바이트씩 있음.
        record_size = 20
        count = len(data) // record_size
        for i in range(count):
            record = data[i * record_size:(i + 1) * record_size]
            (char_id, x, y, width, height, xoffset, yoffset,
             xadvance, page, chnl) = struct.unpack("<IHHHHhhHBb", record)
            glyph = Glyph(char_id, x, y, width, height, xoffset, yoffset, xadvance, page, chnl)
            self.glyphs[char_id] = glyph

    def _parse_kernings_block(self, data):
        # 각 커닝 정보는 10바이트
        record_size = 10
        count = len(data) // record_size
        for i in range(count):
            record = data[i * record_size:(i + 1) * record_size]
            first, second, amount = struct.unpack("<IIh", record)
            self.kernings[(first, second)] = amount

def render_text(text, bmfont, atlas_images):
    """
    BMFont와 atlas_images(dict: page index -> PIL Image)를 이용하여 text를 렌더링한 이미지를 반환합니다.
    이 함수는 줄바꿈 문자("##")를 처리하며, 줄 사이 간격은 2 픽셀로 설정되어 있습니다.
    """
    # BMFont common 정보에서 기준(라인 높이, base) 가져오기
    line_height = bmfont.common.get('lineHeight', list(atlas_images.values())[0].height)
    base_line = bmfont.common.get('base', 0)
    line_spacing = 4  # 줄 사이 간격

    # 각 글자의 위치를 계산하여 전체 텍스트의 bounding box를 구함.
    x_cursor = 0
    y_cursor = 0
    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')

    render_infos = []
    prev_char = None

    for ch in text:
        if ch == "^":
            # 줄바꿈 시 x 커서를 초기화하고 y 커서를 다음 줄로 이동
            x_cursor = 0
            y_cursor += line_height - line_spacing
            prev_char = None
            continue

        char_code = ord(ch)
        glyph = bmfont.glyphs.get(char_code)
        if glyph is None:
            # 해당 문자가 없으면 공백 처리: 일반적으로 fontSize의 절반 정도 이동
            x_cursor += bmfont.info.get('fontSize', line_height) // 2
            prev_char = None
            continue

        # 커닝 조정 (이전 글자가 있으면)
        kern = 0
        if prev_char is not None:
            kern = bmfont.kernings.get((prev_char, char_code), 0)
        x_cursor += kern

        # 글리프의 출력 좌표 계산: 현재 커서 위치에 xoffset, yoffset, 그리고 현재 줄의 y_cursor를 반영
        glyph_x = x_cursor + glyph.xoffset
        glyph_y = y_cursor + base_line + glyph.yoffset
        render_infos.append((glyph, glyph_x, glyph_y))
        
        # bounding box 업데이트
        min_x = min(min_x, glyph_x)
        min_y = min(min_y, glyph_y)
        max_x = max(max_x, glyph_x + glyph.width)
        max_y = max(max_y, glyph_y + glyph.height)
        
        x_cursor += glyph.xadvance
        prev_char = char_code

    # 텍스트가 없을 경우 빈 이미지를 반환
    if min_x == float('inf') or min_y == float('inf'):
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    # 최종 이미지 크기 계산 (bounding box)
    out_width = max_x - min_x
    out_height = max_y - min_y

    # 출력 이미지는 투명도를 지원하는 RGBA 모드로 생성
    out_img = Image.new("RGBA", (out_width, out_height), (0, 0, 0, 0))
    
    # 각 글자 이미지를 atlas_images에서 잘라내어 적절한 위치에 복사
    for glyph, gx, gy in render_infos:
        crop_box = (glyph.x, glyph.y, glyph.x + glyph.width, glyph.y + glyph.height)
        page_index = glyph.page
        if page_index not in atlas_images:
            raise ValueError(f"페이지 {page_index}에 해당하는 아틀라스 이미지가 제공되지 않았습니다.")
        current_atlas = atlas_images[page_index]
        glyph_img = current_atlas.crop(crop_box)
        pos = (gx - min_x, gy - min_y)
        out_img.alpha_composite(glyph_img, dest=pos)
    
    return out_img

def main():
    parser = argparse.ArgumentParser(
        description="BMFont3 바이너리 fnt와 PNG 아틀라스들로 텍스트 이미지를 생성합니다."
    )
    parser.add_argument("fnt", help="BMFont 바이너리 fnt 파일 경로")
    parser.add_argument("png", nargs="+", help="폰트 아틀라스 PNG 이미지 파일 경로들 (하나 이상)")
    parser.add_argument("text", help="렌더링할 텍스트 (예: '다람쥐\\n다람쥐')")
    parser.add_argument("--out", default="output.png", help="출력 이미지 파일명 (기본: output.png)")
    args = parser.parse_args()

    # BMFont 파싱
    bmfont = BMFont()
    try:
        bmfont.load(args.fnt)
    except Exception as e:
        print("fnt 파일 파싱 실패:", e)
        return

    # 아틀라스 이미지들 열기
    atlas_images = {}
    # 단일 PNG가 제공되면 BMFont의 페이지 수와 상관없이 모두 같은 이미지를 사용합니다.
    if len(args.png) == 1:
        try:
            atlas_img = Image.open(args.png[0]).convert("RGBA")
        except Exception as e:
            print("PNG 파일 열기 실패:", e)
            return
        page_count = bmfont.common.get('pages', 1)
        for i in range(page_count):
            atlas_images[i] = atlas_img
    else:
        # 여러 PNG 파일이 제공된 경우, 순서대로 페이지 0, 1, 2, ...에 매핑합니다.
        for i, png_path in enumerate(args.png):
            try:
                atlas_images[i] = Image.open(png_path).convert("RGBA")
            except Exception as e:
                print(f"PNG 파일 열기 실패 ({png_path}):", e)
                return

    # 텍스트 렌더링 및 출력
    out_img = render_text(args.text, bmfont, atlas_images)
    out_img.save(args.out)
    print("텍스트 렌더링 완료. 출력 파일:", args.out)

if __name__ == "__main__":
    main()
