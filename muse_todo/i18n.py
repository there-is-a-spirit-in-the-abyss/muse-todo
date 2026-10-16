"""Human text only. Protocol fields, user content and identifiers stay unchanged."""
import argparse
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


LOCALES = ('en-US', 'es', 'pt')

# English messages are also stable lookup keys, so default installations retain
# their original validation messages. Keep interpolated data outside the catalog.
MESSAGES = {
    'unsupported locale; choose en-US, es, or pt': ('Idioma no compatible; elija en-US, es o pt', 'Idioma não suportado; escolha en-US, es ou pt'),
    'locale differs from initialized configuration; use settings.set': ('El idioma difiere de la configuración inicial; use settings.set', 'O idioma difere da configuração inicial; use settings.set'),
    'time must be an ISO8601 string with timezone': ('La hora debe ser texto ISO8601 con zona horaria', 'A hora deve ser texto ISO8601 com fuso horário'),
    'invalid ISO8601 time': ('Hora ISO8601 no válida', 'Hora ISO8601 inválida'),
    'time must include timezone': ('La hora debe incluir zona horaria', 'A hora deve incluir fuso horário'),
    'command must be an object': ('El comando debe ser un objeto', 'O comando deve ser um objeto'),
    'command must be text': ('El comando debe ser texto', 'O comando deve ser texto'),
    'database missing; run init explicitly': ('Falta la base de datos; ejecute init explícitamente', 'Base de dados ausente; execute init explicitamente'),
    'unsupported database schema': ('Esquema de base de datos no compatible', 'Esquema da base de dados não suportado'),
    'unknown command': ('Comando desconocido', 'Comando desconhecido'),
    'IANA timezone unavailable; use UTC or install system tzdata': ('Zona horaria IANA no disponible; use UTC o instale tzdata en el sistema', 'Fuso horário IANA indisponível; use UTC ou instale tzdata no sistema'),
    'existing database is not Muse Todo V1; preserve it': ('La base de datos existente no es Muse Todo V1; consérvela', 'A base de dados existente não é Muse Todo V1; preserve-a'),
    'timezone differs from initialized configuration': ('La zona horaria difiere de la configuración inicial', 'O fuso horário difere da configuração inicial'),
    'id required': ('Se requiere id', 'id é obrigatório'),
    'remote job id must be nonempty text, at most 500 characters': ('El identificador del trabajo remoto debe ser texto no vacío de hasta 500 caracteres', 'O identificador do trabalho remoto deve ser texto não vazio com até 500 caracteres'),
    'delivery token must be nonempty text, at most 255 characters': ('El token de entrega debe ser texto no vacío de hasta 255 caracteres', 'O token de entrega deve ser texto não vazio com até 255 caracteres'),
    'todo not found': ('Tarea no encontrada', 'Tarefa não encontrada'),
    'include_deleted must be boolean': ('include_deleted debe ser booleano', 'include_deleted deve ser booleano'),
    'invalid status filter': ('Filtro de estado no válido', 'Filtro de estado inválido'),
    'query must be text': ('query debe ser texto', 'query deve ser texto'),
    'request_id reused with different content': ('request_id reutilizado con contenido diferente', 'request_id reutilizado com conteúdo diferente'),
    'version conflict; reread todo before changing it': ('Conflicto de versión; vuelva a leer la tarea antes de modificarla', 'Conflito de versão; leia novamente a tarefa antes de a alterar'),
    'todo is deleted': ('La tarea está eliminada', 'A tarefa foi eliminada'),
    'changes must be a nonempty object': ('changes debe ser un objeto no vacío', 'changes deve ser um objeto não vazio'),
    'invalid status': ('Estado no válido', 'Estado inválido'),
    'reminder must be an object': ('reminder debe ser un objeto', 'reminder deve ser um objeto'),
    'invalid reminder mode': ('Modo de recordatorio no válido', 'Modo de lembrete inválido'),
    'times only permitted for custom reminders': ('times solo se permite para recordatorios custom', 'times só é permitido para lembretes custom'),
    'custom reminders require 1..10 times': ('Los recordatorios custom requieren de 1 a 10 horas', 'Os lembretes custom exigem de 1 a 10 horas'),
    'explicit reminders must be in the future': ('Los recordatorios explícitos deben ser futuros', 'Os lembretes explícitos devem ser futuros'),
    'a complete native cron snapshot is required; partial lists are unsafe': ('Se requiere una instantánea completa del cron nativo; las listas parciales no son seguras', 'É necessário um retrato completo do cron nativo; listas parciais não são seguras'),
    'cron snapshot must be from the last 60 seconds': ('La instantánea cron debe ser de los últimos 60 segundos', 'O retrato cron deve ser dos últimos 60 segundos'),
    'snapshot jobs must be an array': ('jobs de la instantánea debe ser una lista', 'jobs do retrato deve ser uma lista'),
    'job must be an object': ('El trabajo debe ser un objeto', 'O trabalho deve ser um objeto'),
    'snapshot contains duplicate job ids': ('La instantánea contiene identificadores de trabajo duplicados', 'O retrato contém identificadores de trabalho duplicados'),
    'job marker must be text': ('El marcador del trabajo debe ser texto', 'O marcador do trabalho deve ser texto'),
    'unknown sync command': ('Comando de sincronización desconocido', 'Comando de sincronização desconhecido'),
    'external operation must finish or be explicitly recovered after quiescence': ('La operación externa debe finalizar o recuperarse explícitamente después de confirmar su detención', 'A operação externa deve terminar ou ser recuperada explicitamente após confirmar a sua paragem'),
    'snapshot predates an external operation; read sync.status then fetch native jobs again': ('La instantánea es anterior a una operación externa; lea sync.status y vuelva a obtener los trabajos nativos', 'O retrato é anterior a uma operação externa; leia sync.status e obtenha novamente os trabalhos nativos'),
    'unknown operation': ('Operación desconocida', 'Operação desconhecida'),
    'remote_id differs from reserved operation': ('remote_id difiere de la operación reservada', 'remote_id difere da operação reservada'),
    'conflicting ack': ('Confirmación contradictoria', 'Confirmação contraditória'),
    'operation is already closed; take a new snapshot': ('La operación ya está cerrada; obtenga una nueva instantánea', 'A operação já está encerrada; obtenha um novo retrato'),
    'ensure the previous native invocation has stopped before recovery': ('Confirme que la invocación nativa anterior se ha detenido antes de recuperar', 'Confirme que a invocação nativa anterior parou antes da recuperação'),
    'operation cannot be recovered in current state': ('La operación no se puede recuperar en su estado actual', 'A operação não pode ser recuperada no estado atual'),
    'fetch a new complete native snapshot; never replay the old intent': ('Obtenga una nueva instantánea nativa completa; nunca repita la intención anterior', 'Obtenha um novo retrato nativo completo; nunca repita a intenção anterior'),
    'outcome must be not_applied or unknown': ('outcome debe ser not_applied o unknown', 'outcome deve ser not_applied ou unknown'),
    'operation already closed or uncertain': ('La operación ya está cerrada o es incierta', 'A operação já está encerrada ou é incerta'),
    'unknown delivery command': ('Comando de entrega desconocido', 'Comando de entrega desconhecido'),
    'unknown reminder': ('Recordatorio desconocido', 'Lembrete desconhecido'),
    'stale delivery token': ('Token de entrega obsoleto', 'Token de entrega desatualizado'),
    'conflicting delivery receipt': ('Comprobante de entrega contradictorio', 'Comprovativo de entrega contraditório'),
    'delivery requires version and at from native payload': ('La entrega requiere version y at del contenido nativo', 'A entrega exige version e at do conteúdo nativo'),
    'stale or inactive reminder': ('Recordatorio obsoleto o inactivo', 'Lembrete desatualizado ou inativo'),
    'outside delivery time window (0..900 seconds late)': ('Fuera del plazo de entrega (de 0 a 900 segundos de retraso)', 'Fora do prazo de entrega (de 0 a 900 segundos de atraso)'),
    'delivery already claimed or delivered': ('Entrega ya reservada o realizada', 'Entrega já reservada ou realizada'),
    'Reminder: {title}': ('Recordatorio: {title}', 'Lembrete: {title}'),
    'invalid JSON': ('JSON no válido', 'JSON inválido'),
    'invalid text encoding; use UTF-8': ('Codificación no válida; use UTF-8', 'Codificação inválida; use UTF-8'),
    'could not read or write file': ('No se pudo leer o escribir el archivo', 'Não foi possível ler ou escrever o ficheiro'),
    'database operation failed': ('Falló la operación de base de datos', 'A operação da base de dados falhou'),
    'invalid data': ('Datos no válidos', 'Dados inválidos'),
    'Muse Todo JSON command runner; never calls cron': ('Ejecutor de comandos JSON de Muse Todo; nunca llama a cron', 'Executor de comandos JSON do Muse Todo; nunca chama cron'),
    'Explicit SQLite path; use a new V1 path': ('Ruta SQLite explícita; use una ruta V1 nueva', 'Caminho SQLite explícito; use um novo caminho V1'),
    'UTF-8 JSON file; default stdin': ('Archivo JSON UTF-8; entrada estándar por defecto', 'Ficheiro JSON UTF-8; entrada padrão por omissão'),
    'Show this help message and exit': ('Mostrar esta ayuda y salir', 'Mostrar esta ajuda e sair'),
    'usage: ': ('uso: ', 'uso: '),
    'options': ('opciones', 'opções'),
    'positional arguments': ('argumentos posicionales', 'argumentos posicionais'),
    'error': ('error', 'erro'),
    'Explicit old-PoC backup and reversible quarantine; never removes cron': ('Copia de seguridad e aislamiento reversible del PoC antiguo; nunca elimina cron', 'Cópia de segurança e isolamento reversível do PoC antigo; nunca remove cron'),
    'Assert old runners and identified PoC cron have stopped': ('Confirmar que los procesos antiguos y cron PoC identificados se han detenido', 'Confirmar que os processos antigos e cron PoC identificados pararam'),
    'Language for this invocation (en-US, es, pt)': ('Idioma para esta invocación (en-US, es, pt)', 'Idioma para esta invocação (en-US, es, pt)'),
    'target escapes workspace': ('El destino está fuera del espacio de trabajo', 'O destino está fora do espaço de trabalho'),
    'symlink/junction target is not safe to quarantine': ('No es seguro aislar un enlace simbólico o una unión', 'Não é seguro isolar uma ligação simbólica ou junção'),
    'backup must be outside the old Skill/data directories': ('La copia debe estar fuera de los directorios antiguos de Skill y datos', 'A cópia deve estar fora dos diretórios antigos de Skill e dados'),
    'backup destination already exists; choose a new directory': ('El destino de la copia ya existe; elija un directorio nuevo', 'O destino da cópia já existe; escolha um novo diretório'),
    'SQLite backup failed integrity check': ('La copia SQLite falló la comprobación de integridad', 'A cópia SQLite falhou a verificação de integridade'),
    'stop old runners and positively identified PoC cron jobs before quarantine': ('Detenga los procesos antiguos y los trabajos cron PoC identificados antes del aislamiento', 'Pare os processos antigos e os trabalhos cron PoC identificados antes do isolamento'),
    'source changed while backing up; quiesce and take another backup': ('El origen cambió durante la copia; detenga los procesos y haga otra copia', 'A origem mudou durante a cópia; pare os processos e faça outra cópia'),
    'unknown Skill files preserved; inspect and separate them before quarantine': ('Archivos Skill desconocidos conservados; revíselos y sepárelos antes del aislamiento', 'Ficheiros Skill desconhecidos preservados; examine-os e separe-os antes do isolamento'),
    'invalid backup manifest path': ('Ruta del manifiesto de copia no válida', 'Caminho do manifesto da cópia inválido'),
    'backup missing or changed': ('La copia falta o ha cambiado', 'A cópia está ausente ou foi alterada'),
    'new source file appeared since backup': ('Apareció un archivo de origen nuevo después de la copia', 'Surgiu um novo ficheiro de origem após a cópia'),
    'new unknown Skill file appeared; preserving all sources': ('Apareció un archivo Skill desconocido; se conservan todos los originales', 'Surgiu um ficheiro Skill desconhecido; todas as origens são preservadas'),
    'invalid source manifest path': ('Ruta del manifiesto de origen no válida', 'Caminho do manifesto de origem inválido'),
    'both source and quarantine target exist': ('Existen tanto el origen como el destino de aislamiento', 'A origem e o destino de isolamento existem'),
    'source changed since backup; preserve it and back up again': ('El origen cambió desde la copia; consérvelo y haga otra copia', 'A origem mudou desde a cópia; preserve-a e faça outra cópia'),
    'cron and shared configuration require Agent inspection; never removed by this tool': ('El cron y la configuración compartida requieren revisión del Agent; esta herramienta nunca los elimina', 'O cron e a configuração partilhada exigem inspeção do Agent; esta ferramenta nunca os remove'),
}

PATTERNS = (
    (r'(.+) must be nonempty text, at most (\d+) characters', '{0} debe ser texto no vacío de hasta {1} caracteres', '{0} deve ser texto não vazio com até {1} caracteres'),
    (r'unknown fields: (.+)', 'Campos desconocidos: {0}', 'Campos desconhecidos: {0}'),
    (r'duplicate JSON key: (.+)', 'Clave JSON duplicada: {0}', 'Chave JSON duplicada: {0}'),
    (r'invalid JSON constant: (.+)', 'Constante JSON no válida: {0}', 'Constante JSON inválida: {0}'),
    (r'expected a regular file: (.+)', 'Se esperaba un archivo normal: {0}', 'Era esperado um ficheiro normal: {0}'),
    (r'unrecognized arguments: (.+)', 'Argumentos no reconocidos: {0}', 'Argumentos não reconhecidos: {0}'),
    (r'the following arguments are required: (.+)', 'Se requieren los siguientes argumentos: {0}', 'Os seguintes argumentos são obrigatórios: {0}'),
    (r'argument (.+): expected one argument', 'El argumento {0} requiere un valor', 'O argumento {0} exige um valor'),
    (r'argument (.+): invalid choice: (.+) \(choose from (.+)\)', 'El argumento {0} tiene una opción no válida: {1} (elija entre {2})', 'O argumento {0} tem uma opção inválida: {1} (escolha entre {2})'),
)


def translate(message, locale='en-US', **values):
    if locale in ('es', 'pt'):
        index = 0 if locale == 'es' else 1
        if message in MESSAGES:
            message = MESSAGES[message][index]
        else:
            for pattern, es, pt in PATTERNS:
                match = re.fullmatch(pattern, message, flags=re.DOTALL)
                if match:
                    return (es if index == 0 else pt).format(*match.groups())
    return message.format(**values) if values else message


def read_locale(db):
    row = db.execute("SELECT value FROM meta WHERE key='locale'").fetchone()
    return row[0] if row and row[0] in LOCALES else 'en-US'


def saved_locale(path):
    """Read without creating files, migrating schemas or holding mutable state."""
    try:
        uri = Path(path).expanduser().resolve().as_uri() + '?mode=ro'
        with closing(sqlite3.connect(uri, uri=True, timeout=15)) as db:
            return read_locale(db)
    except (OSError, sqlite3.Error, ValueError):
        return 'en-US'


def exception_message(exc, locale):
    # Imported lazily to avoid the service/catalog import cycle.
    from .service import TodoError
    if isinstance(exc, TodoError):
        return translate(str(exc), locale)
    if isinstance(exc, json.JSONDecodeError):
        message = 'invalid JSON'
    elif isinstance(exc, UnicodeError):
        message = 'invalid text encoding; use UTF-8'
    elif isinstance(exc, OSError):
        message = 'could not read or write file'
    elif isinstance(exc, sqlite3.Error):
        message = 'database operation failed'
    else:
        message = 'invalid data'
    return translate(message, locale)


def option_value(argv, flag, default=None):
    """Bootstrap display language without rejecting malformed CLI arguments.

    The actual parser still validates every argument and produces the error.
    Retain the last complete option so a later missing value can be explained
    in the selected language. Do not inspect tokens after the option terminator.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    value = default
    for index, arg in enumerate(args):
        if arg == '--':
            break
        if arg.startswith(flag + '='):
            value = arg[len(flag) + 1:]
        elif arg == flag and index + 1 < len(args) and not args[index + 1].startswith('-'):
            value = args[index + 1]
    return value


class LocalizedParser(argparse.ArgumentParser):
    def __init__(self, *args, locale='en-US', **kwargs):
        self.locale = locale
        kwargs['add_help'] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = translate('positional arguments', locale)
        self._optionals.title = translate('options', locale)
        self.add_argument('-h', '--help', action='help', help=translate('Show this help message and exit', locale))

    def format_usage(self):
        return super().format_usage().replace('usage: ', translate('usage: ', self.locale), 1)

    def format_help(self):
        return super().format_help().replace('usage: ', translate('usage: ', self.locale), 1)

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f'{self.prog}: {translate("error", self.locale)}: {translate(message, self.locale)}\n')
