import {
  COLOR_ND,
  ETIQUETA_ND,
  INTERVALOS_PROFUNDIDAD,
  RADIO_ND,
  colorPorProfundidad,
  contornoCirculo,
  estiloCirculo,
  intervaloProfundidad,
  leyendaRadio,
  radioPorMagnitud,
} from './escalas';

describe('radioPorMagnitud', () => {
  it('3 + 2,5·M con M acotada a [0, 8]', () => {
    expect(radioPorMagnitud(0)).toBe(3);
    expect(radioPorMagnitud(4)).toBe(13);
    expect(radioPorMagnitud(8)).toBe(23);
  });

  it('acota por arriba y por abajo (magnitudes negativas o ≥ 9)', () => {
    expect(radioPorMagnitud(9.1)).toBe(23);
    expect(radioPorMagnitud(-1.2)).toBe(3);
  });

  it('M null no es 0: radio fijo propio', () => {
    expect(radioPorMagnitud(null)).toBe(RADIO_ND);
    expect(radioPorMagnitud(null)).not.toBe(radioPorMagnitud(0));
    expect(RADIO_ND).toBe(5);
  });

  it('un valor no finito se trata como desconocido', () => {
    expect(radioPorMagnitud(Number.NaN)).toBe(RADIO_ND);
  });
});

describe('intervalos de profundidad (mismos que la API)', () => {
  it('etiquetas de la API, en orden', () => {
    expect(INTERVALOS_PROFUNDIDAD.map((i) => i.etiqueta)).toEqual([
      '< 0',
      '0–10',
      '10–30',
      '30–70',
      '70–150',
      '150–300',
      '300–500',
      '500–700',
      '≥ 700',
    ]);
  });

  it('−5 va a «< 0»; 0 abre «0–10»; 10 abre «10–30»; 700 abre «≥ 700»', () => {
    expect(intervaloProfundidad(-5)?.etiqueta).toBe('< 0');
    expect(intervaloProfundidad(-0.0001)?.etiqueta).toBe('< 0');
    expect(intervaloProfundidad(0)?.etiqueta).toBe('0–10');
    expect(intervaloProfundidad(9.99)?.etiqueta).toBe('0–10');
    expect(intervaloProfundidad(10)?.etiqueta).toBe('10–30');
    expect(intervaloProfundidad(699.9)?.etiqueta).toBe('500–700');
    expect(intervaloProfundidad(700)?.etiqueta).toBe('≥ 700');
    expect(intervaloProfundidad(6000)?.etiqueta).toBe('≥ 700');
  });

  it('null no pertenece a ningún intervalo', () => {
    expect(intervaloProfundidad(null)).toBeNull();
    expect(intervaloProfundidad(Number.NaN)).toBeNull();
  });
});

describe('colorPorProfundidad', () => {
  it('cada intervalo tiene un color distinto y ninguno es el de ND', () => {
    const colores = INTERVALOS_PROFUNDIDAD.map((i) => i.color);
    expect(new Set(colores).size).toBe(INTERVALOS_PROFUNDIDAD.length);
    expect(colores).not.toContain(COLOR_ND);
  });

  it('valores en el borde de un intervalo usan el color del intervalo superior', () => {
    expect(colorPorProfundidad(10)).toBe(INTERVALOS_PROFUNDIDAD[2].color);
    expect(colorPorProfundidad(9.99)).toBe(INTERVALOS_PROFUNDIDAD[1].color);
    expect(colorPorProfundidad(0)).toBe(INTERVALOS_PROFUNDIDAD[1].color);
    expect(colorPorProfundidad(-5)).toBe(INTERVALOS_PROFUNDIDAD[0].color);
    expect(colorPorProfundidad(700)).toBe(INTERVALOS_PROFUNDIDAD[8].color);
  });

  it('null = gris ND, nunca el color de profundidad 0', () => {
    expect(colorPorProfundidad(null)).toBe(COLOR_ND);
    expect(colorPorProfundidad(null)).not.toBe(colorPorProfundidad(0));
  });
});

describe('estiloCirculo', () => {
  it('evento completo: borde continuo, sin etiqueta ND', () => {
    expect(estiloCirculo(5, 35)).toEqual({
      radio: 15.5,
      color: INTERVALOS_PROFUNDIDAD[3].color,
      bordeDiscontinuo: false,
      etiquetaMagnitud: null,
      etiquetaProfundidad: null,
    });
  });

  it('magnitud null: radio fijo, borde discontinuo y «ND»', () => {
    const e = estiloCirculo(null, 12);
    expect(e.radio).toBe(RADIO_ND);
    expect(e.bordeDiscontinuo).toBe(true);
    expect(e.etiquetaMagnitud).toBe(ETIQUETA_ND);
    expect(e.etiquetaProfundidad).toBeNull();
  });

  it('profundidad null: gris ND con borde discontinuo', () => {
    const e = estiloCirculo(3, null);
    expect(e.color).toBe(COLOR_ND);
    expect(e.bordeDiscontinuo).toBe(true);
    expect(e.etiquetaProfundidad).toBe('ND');
  });
});

describe('leyendaRadio', () => {
  it('muestra magnitudes de ejemplo con su radio y la entrada ND', () => {
    const l = leyendaRadio();
    expect(l.map((e) => e.etiqueta)).toEqual(['0', '2', '4', '6', '8', 'ND']);
    expect(l[2]).toEqual({ etiqueta: '4', radio: 13 });
    expect(l[5]).toEqual({ etiqueta: 'ND', radio: RADIO_ND });
  });
});

describe('contornoCirculo', () => {
  it('un evento normal: contorno fino y continuo', () => {
    expect(contornoCirculo(false, false)).toEqual({ grosor: 1, discontinuo: undefined });
  });

  it('un valor desconocido (ND): contorno fino discontinuo', () => {
    expect(contornoCirculo(false, true)).toEqual({ grosor: 1, discontinuo: '3 2' });
  });

  it('un caso sintético: contorno grueso y discontinuo, distinto del de ND', () => {
    const sintetico = contornoCirculo(true, false);
    const nd = contornoCirculo(false, true);
    expect(sintetico.discontinuo).toBeDefined();
    expect(sintetico.grosor).toBeGreaterThan(nd.grosor);
    expect(sintetico.discontinuo).not.toBe(nd.discontinuo);
  });

  it('sintético y además ND: manda la marca de sintético', () => {
    expect(contornoCirculo(true, true)).toEqual(contornoCirculo(true, false));
  });
});