#!/usr/bin/env python3
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESS = ROOT / "prensa"

CONTENT = {
    '20minutos-piramide': ('La nueva pirámide alimentaria estadounidense ha reabierto el debate sobre qué criterios deben guiar las recomendaciones nutricionales y hasta qué punto la evidencia científica debe distinguirse de las decisiones políticas.', 'La pieza de 20minutos analiza la nueva pirámide nutricional de EE. UU. y recoge la perspectiva de especialistas sobre sus implicaciones y sobre cómo se construyen este tipo de recomendaciones.', 'La aparición se centra en un tema especialmente relevante para la comunicación científica: cómo interpretar recomendaciones nutricionales cuando intervienen criterios científicos, institucionales y políticos.'),
    'actual-fruveg': ('La publicación aborda la sustitución de proteína animal por proteína vegetal y sus posibles implicaciones dentro de los patrones dietéticos habituales.', 'Actual FruVeg recoge información relacionada con el cambio de fuentes de proteína animal a vegetal y presenta la cuestión desde la perspectiva de la alimentación y la nutrición.', 'La pieza conecta la investigación sobre sustituciones dietéticas con una pregunta práctica: qué puede ocurrir cuando cambia la fuente de proteína sin considerar únicamente un alimento de forma aislada.'),
    'agencia-sinc-nutricion': ('Los estudios de nutrición pueden llegar a conclusiones aparentemente contradictorias cuando cambian el diseño, la población, la exposición estudiada o la forma de interpretar los resultados.', 'La Agencia SINC aborda las razones por las que distintos estudios de nutrición pueden ofrecer resultados diferentes y plantea la importancia de interpretar la evidencia en su contexto.', 'La pieza pone el foco en una de las cuestiones centrales de la divulgación científica: entender por qué una aparente contradicción no implica necesariamente que la ciencia no sepa qué ocurre.'),
    'carne-roja': ('La evidencia sobre carne roja no puede interpretarse de forma aislada: el efecto observado depende también de qué alimento ocupa su lugar dentro de la dieta.', 'Esta publicación de Nutreconciencia recoge la cuestión de la carne roja y la necesidad de interpretar sus asociaciones con la salud teniendo en cuenta el alimento de comparación.', 'La ficha destaca la importancia de las comparaciones dietéticas y del contexto para evitar conclusiones simplificadas sobre un alimento concreto.'),
    'el-mundo': ('La evidencia sobre carne roja y salud cardiovascular requiere interpretar los resultados teniendo en cuenta el diseño de los estudios y, especialmente, con qué alimentos se compara su consumo.', 'El Mundo aborda qué podemos concluir realmente de la investigación disponible sobre carne roja y salud y recoge la importancia de valorar la evidencia en su contexto.', 'La pieza se centra en una cuestión recurrente en nutrición: una misma exposición puede asociarse con resultados diferentes dependiendo del patrón dietético y de la comparación utilizada.'),
    'el-mundo-omniveg': ('El estudio OMNIVEG comparó una dieta mediterránea tradicional con una dieta mediterránea vegana en hombres sanos, manteniendo controlada la ingesta energética.', 'El Mundo recoge los resultados del estudio OMNIVEG y aborda los efectos de sustituir fuentes de proteína animal por fuentes de proteína vegetal dentro de un patrón de dieta mediterránea.', 'La pieza acerca al público general los resultados de una investigación sobre cómo la composición del patrón dietético puede relacionarse con distintos indicadores de salud y enlaza directamente con la publicación original.'),
    'eldiario-greenwashing': ('La responsabilidad ambiental de la alimentación también implica analizar cómo las empresas comunican sus compromisos climáticos y qué evidencia respalda esas afirmaciones.', 'elDiario.es aborda la responsabilidad climática y ética de los supermercados ante el greenwashing y recoge la discusión sobre la comunicación de sostenibilidad en el sector alimentario.', 'La aparición conecta la investigación y la divulgación sobre alimentación sostenible con un problema de comunicación pública: distinguir compromisos ambientales verificables de mensajes de marketing.'),
    'instituto-nutrigenomica': ('La investigación en nutrición abarca cuestiones que van desde la microbiota y el envejecimiento hasta la relación entre alimentación y salud planetaria.', 'El Instituto de Nutrigenómica reúne avances relacionados con microbiota, salud planetaria y envejecimiento dentro del panorama actual de investigación en nutrición.', 'La pieza sitúa el trabajo en nutrición dentro de un marco amplio en el que convergen salud humana, sostenibilidad y procesos biológicos relacionados con el envejecimiento.'),
    'la-vanguardia-seeds': ('El debate sobre los aceites de semillas muestra cómo una afirmación nutricional puede convertirse en un mensaje absoluto cuando se pierde el contexto de la evidencia.', 'La Vanguardia aborda la afirmación de que los aceites de semillas son prácticamente un veneno y un problema de salud pública, y recoge la perspectiva de Miguel López Moreno sobre esta cuestión.', 'La entrevista se centra en cómo valorar afirmaciones contundentes sobre alimentos y en la necesidad de distinguir entre una hipótesis, una asociación y una conclusión causal.'),
    'la-voz-galicia-meat': ('El consumo de carne y su relación con la salud cardiovascular debe interpretarse dentro del conjunto de la dieta y teniendo en cuenta qué alimentos pueden sustituirla.', 'La Voz de Galicia recoge la perspectiva de Miguel López Moreno sobre la relación entre un consumo bajo de carne y el riesgo cardiovascular.', 'La pieza aborda la carne desde una perspectiva de sustitución dietética, evitando interpretar el efecto de un alimento sin considerar el patrón alimentario en el que se integra.'),
    'la-voz-galicia-omniveg': ('El estudio OMNIVEG exploró qué ocurre cuando se sustituye la proteína animal por proteína vegetal dentro de un patrón de dieta mediterránea.', 'La Voz de Galicia presenta los resultados del estudio OMNIVEG y destaca los cambios observados en marcadores como el colesterol y la presión arterial al comparar ambos patrones dietéticos.', 'La noticia traduce los resultados de un ensayo controlado al lenguaje divulgativo y pone el foco en los efectos de una sustitución concreta dentro de la dieta mediterránea.'),
    'pcrm-omniveg': ('El estudio OMNIVEG comparó una dieta mediterránea vegana con una dieta mediterránea convencional para estudiar sus efectos sobre distintos indicadores de salud metabólica.', 'Physicians Committee for Responsible Medicine presenta los principales resultados del estudio OMNIVEG y destaca la comparación entre ambos patrones dietéticos.', 'La pieza ofrece una lectura divulgativa de un ensayo controlado centrado en la composición de la dieta y sus efectos metabólicos.'),
    'perfil-fit-generation': ('La investigación, la docencia y la divulgación forman parte de una misma trayectoria profesional centrada en interpretar y comunicar la evidencia nutricional.', 'El perfil de Fit Generation presenta la trayectoria de Miguel López Moreno y sus líneas de trabajo en investigación, formación y divulgación en nutrición.', 'La ficha recoge el perfil profesional y conecta la actividad investigadora con la formación y la comunicación pública de la ciencia.'),
    'plantrician-omniveg': ('El estudio OMNIVEG comparó una dieta mediterránea tradicional con una dieta mediterránea vegana en hombres sanos bajo condiciones controladas.', 'Plantrician Project ofrece una lectura divulgativa del estudio OMNIVEG y explica los principales elementos del trabajo y de la comparación entre ambos patrones dietéticos.', 'La pieza está centrada específicamente en el estudio OMNIVEG y facilita el acceso a su interpretación desde el ámbito de la nutrición basada en plantas.'),
    'podcast-dieta-mediterranea': ('La dieta mediterránea puede analizarse más allá de etiquetas generales, atendiendo a la calidad de los alimentos, el patrón dietético y la evidencia que sustenta sus beneficios.', 'La conversación aborda la dieta mediterránea, las dietas basadas en plantas y la interpretación de la evidencia nutricional desde una perspectiva crítica.', 'La aparición amplía el trabajo de investigación y divulgación a un formato de conversación en el que se abordan cuestiones prácticas sobre nutrición y evidencia.'),
    'the-new-york-times': ('La investigación sobre carne roja y salud cardiovascular no ofrece una respuesta sencilla cuando se ignoran el contexto dietético y las comparaciones entre alimentos.', 'The New York Times aborda qué dice realmente la investigación sobre carne roja y salud cardiovascular y pone el foco en cómo interpretar la evidencia disponible.', 'La pieza es especialmente relevante por trasladar al público general una cuestión compleja de epidemiología y nutrición sin reducirla a una respuesta binaria sobre un único alimento.'),
    'the-times': ('Las conclusiones sobre carne roja y salud cardiovascular dependen de cómo se diseñan los estudios, con qué alimentos se compara la carne y qué posibles fuentes de financiación pueden influir en la interpretación.', 'The Times analiza la controversia científica alrededor de la carne roja y la salud cardiovascular y aborda también el contexto de la evidencia disponible.', 'La pieza pone en primer plano la necesidad de interpretar la investigación nutricional atendiendo al diseño del estudio, las comparaciones dietéticas y los posibles conflictos de interés.'),
    'vozpopuli-omniveg': ('La dieta mediterránea vegana plantea preguntas sobre sus posibles beneficios y sobre los aspectos nutricionales que conviene considerar cuando se modifica un patrón dietético.', 'Vozpópuli aborda los posibles beneficios y algunos inconvenientes de la dieta mediterránea vegana y recoge el debate alrededor de este patrón de alimentación.', 'La pieza presenta la dieta mediterránea vegana desde una perspectiva divulgativa y permite contextualizar sus posibles efectos dentro del conjunto de la alimentación.'),
    'washington-post': ('Las respuestas sobre carne roja y salud siguen estando condicionadas por la incertidumbre de parte de la investigación y por la forma en que se comparan distintos patrones dietéticos.', 'The Washington Post aborda si la carne roja es perjudicial para la salud y destaca los límites de la evidencia disponible para obtener una respuesta definitiva.', 'La pieza pone el foco en una cuestión esencial para interpretar la ciencia de la nutrición: reconocer la incertidumbre sin convertirla en ausencia de evidencia.'),
}

def replace_first_paragraph_after_heading(text: str, heading_pattern: str, new_text: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf'(<(?:strong|h2|h3)[^>]*>\s*{heading_pattern}\s*</(?:strong|h2|h3)>\s*)'
        r'<p[^>]*>.*?</p>',
        re.I | re.S,
    )
    m = pattern.search(text)
    if not m:
        return text, False
    replacement = m.group(1) + f"<p>{new_text}</p>"
    return text[:m.start()] + replacement + text[m.end():], True

def replace_first_lead(text: str, title: str, new_text: str) -> tuple[str, bool]:
    # Find the first paragraph after the main title/H1. If the current text is
    # already custom, replace only when it is one of the template-like leads.
    m_h1 = re.search(r"<h1[^>]*>.*?</h1>", text, re.I | re.S)
    if not m_h1:
        return text, False
    tail = text[m_h1.end():]
    m_p = re.search(r"<p[^>]*>.*?</p>", tail, re.I | re.S)
    if not m_p:
        return text, False

    current = re.sub(r"<[^>]+>", " ", m_p.group(0))
    current = re.sub(r"\s+", " ", current).strip()
    generic = (
        "Aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud."
        "Una aparición pública vinculada a investigación, divulgación o análisis de nutrición y salud."
    )
    if current not in generic and not current.startswith("La publicación de ") and not current.startswith("La noticia de "):
        return text, False

    new_tag = f"<p>{new_text}</p>"
    start = m_h1.end() + m_p.start()
    end = m_h1.end() + m_p.end()
    return text[:start] + new_tag + text[end:], True

def main():
    pages = sorted(PRESS.glob("*/index.html"))
    modified = 0
    notes = []

    for page in pages:
        slug = page.parent.name
        if slug not in CONTENT:
            notes.append(f"{slug}: no editorial mapping")
            continue

        lead, publication, review = CONTENT[slug]
        text = page.read_text(encoding="utf-8", errors="ignore")
        updated = text
        changed = False

        updated, c = replace_first_lead(updated, slug, lead)
        changed |= c

        updated, c = replace_first_paragraph_after_heading(
            updated, r"La publicación|La\s+publicaci[oó]n", publication
        )
        changed |= c

        updated, c = replace_first_paragraph_after_heading(
            updated, r"BREVE\s+RESE[NÑ]A|Breve\s+rese[nñ]a", review
        )
        changed |= c

        if changed:
            page.write_text(updated, encoding="utf-8")
            modified += 1
        else:
            notes.append(f"{slug}: structure did not match; left unchanged")

    print("=" * 72)
    print("STEP 8D — EDITORIAL PRESS PAGES")
    print("=" * 72)
    print(f"Press pages scanned: {len(pages)}")
    print(f"Pages modified: {modified}")
    print(f"Pages requiring structural review: {len(notes)}")
    if notes:
        print("\nNOTES:")
        for n in notes:
            print("-", n)
    print("\nOnly press-page body copy was changed.")

if __name__ == "__main__":
    main()
