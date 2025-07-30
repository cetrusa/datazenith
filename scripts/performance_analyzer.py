"""
Sistema de análisis de rendimiento automático para Django
Identifica cuellos de botella y sugiere optimizaciones
"""
import os
import re
import subprocess
from pathlib import Path

class DjangoPerformanceAnalyzer:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.issues = []
        
    def analyze_all(self):
        """Ejecuta todos los análisis de rendimiento"""
        print("🔍 INICIANDO ANÁLISIS DE RENDIMIENTO COMPLETO...")
        print("=" * 60)
        
        self.analyze_queries()
        self.analyze_views()
        self.analyze_templates()
        self.analyze_middleware()
        self.analyze_static_files()
        
        self.generate_report()
        
    def analyze_queries(self):
        """Analiza consultas problemáticas en el código"""
        print("\n📊 ANALIZANDO CONSULTAS DE BASE DE DATOS...")
        
        # Patrones problemáticos
        patterns = {
            'objects.all()': 'Posible problema N+1 - considera usar only() o defer()',
            'for.*in.*objects': 'Loop sobre QuerySet - considera prefetch_related()',
            '\.get\(.*pk=': 'Considera usar get_object_or_404()',
            'len\(.*objects': 'Usa .count() en lugar de len() para QuerySets'
        }
        
        py_files = list(self.project_path.rglob('*.py'))
        
        for file_path in py_files:
            if 'migrations' in str(file_path) or '__pycache__' in str(file_path):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                for pattern, suggestion in patterns.items():
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        self.issues.append({
                            'type': 'Database Query',
                            'file': str(file_path.relative_to(self.project_path)),
                            'line': line_num,
                            'issue': pattern,
                            'suggestion': suggestion
                        })
            except Exception as e:
                continue
                
    def analyze_views(self):
        """Analiza vistas para problemas de rendimiento"""
        print("\n🎯 ANALIZANDO VISTAS...")
        
        view_files = list(self.project_path.rglob('views.py'))
        
        for file_path in view_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Detectar vistas sin caché
                if 'cache' not in content.lower():
                    self.issues.append({
                        'type': 'View Performance',
                        'file': str(file_path.relative_to(self.project_path)),
                        'line': 1,
                        'issue': 'Sin sistema de caché',
                        'suggestion': 'Considera agregar caché con @cache_page o cache.get/set'
                    })
                    
                # Detectar vistas complejas
                lines = content.split('\n')
                current_function = None
                function_line_count = 0
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('def ') or line.strip().startswith('class '):
                        if current_function and function_line_count > 50:
                            self.issues.append({
                                'type': 'View Complexity',
                                'file': str(file_path.relative_to(self.project_path)),
                                'line': i - function_line_count,
                                'issue': f'Función/clase muy larga ({function_line_count} líneas)',
                                'suggestion': 'Considera dividir en funciones más pequeñas'
                            })
                        current_function = line.strip()
                        function_line_count = 0
                    else:
                        function_line_count += 1
                        
            except Exception as e:
                continue
                
    def analyze_templates(self):
        """Analiza templates para problemas de rendimiento"""
        print("\n📄 ANALIZANDO TEMPLATES...")
        
        template_files = list(self.project_path.rglob('*.html'))
        
        for file_path in template_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Detectar loops anidados
                for_count = content.count('{% for')
                if for_count > 3:
                    self.issues.append({
                        'type': 'Template Performance',
                        'file': str(file_path.relative_to(self.project_path)),
                        'line': 1,
                        'issue': f'Múltiples loops ({for_count})',
                        'suggestion': 'Considera mover lógica compleja a las vistas'
                    })
                    
                # Detectar templates sin caché
                if '{% load cache %}' not in content:
                    self.issues.append({
                        'type': 'Template Caching',
                        'file': str(file_path.relative_to(self.project_path)),
                        'line': 1,
                        'issue': 'Sin etiquetas de caché',
                        'suggestion': 'Considera usar {% cache %} para contenido estático'
                    })
                    
            except Exception as e:
                continue
                
    def analyze_middleware(self):
        """Analiza middleware por orden y optimización"""
        print("\n⚙️ ANALIZANDO MIDDLEWARE...")
        
        settings_files = list(self.project_path.rglob('settings*.py'))
        
        for file_path in settings_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if 'MIDDLEWARE' in content:
                    # Verificar orden del middleware
                    if 'GZipMiddleware' in content:
                        lines = content.split('\n')
                        middleware_section = False
                        gzip_position = -1
                        
                        for i, line in enumerate(lines):
                            if 'MIDDLEWARE' in line and '=' in line:
                                middleware_section = True
                            elif middleware_section and 'GZip' in line:
                                gzip_position = i
                            elif middleware_section and ']' in line:
                                break
                                
                        if gzip_position > 0:
                            self.issues.append({
                                'type': 'Middleware Order',
                                'file': str(file_path.relative_to(self.project_path)),
                                'line': gzip_position + 1,
                                'issue': 'GZipMiddleware no está al principio',
                                'suggestion': 'Mover GZipMiddleware al inicio para mejor compresión'
                            })
                            
            except Exception as e:
                continue
                
    def analyze_static_files(self):
        """Analiza archivos estáticos"""
        print("\n📁 ANALIZANDO ARCHIVOS ESTÁTICOS...")
        
        static_dirs = ['static', 'staticfiles']
        
        for static_dir in static_dirs:
            static_path = self.project_path / static_dir
            if static_path.exists():
                # Verificar archivos CSS grandes
                css_files = list(static_path.rglob('*.css'))
                for css_file in css_files:
                    try:
                        size_mb = css_file.stat().st_size / (1024 * 1024)
                        if size_mb > 1:  # Archivos CSS mayores a 1MB
                            self.issues.append({
                                'type': 'Static Files',
                                'file': str(css_file.relative_to(self.project_path)),
                                'line': 1,
                                'issue': f'Archivo CSS grande ({size_mb:.2f}MB)',
                                'suggestion': 'Considera minificar o dividir el archivo'
                            })
                    except Exception:
                        continue
                        
                # Verificar archivos JS grandes
                js_files = list(static_path.rglob('*.js'))
                for js_file in js_files:
                    try:
                        size_mb = js_file.stat().st_size / (1024 * 1024)
                        if size_mb > 1:  # Archivos JS mayores a 1MB
                            self.issues.append({
                                'type': 'Static Files',
                                'file': str(js_file.relative_to(self.project_path)),
                                'line': 1,
                                'issue': f'Archivo JS grande ({size_mb:.2f}MB)',
                                'suggestion': 'Considera minificar o usar CDN'
                            })
                    except Exception:
                        continue
                        
    def generate_report(self):
        """Genera reporte final"""
        print("\n" + "=" * 60)
        print("📋 REPORTE DE ANÁLISIS DE RENDIMIENTO")
        print("=" * 60)
        
        if not self.issues:
            print("✅ ¡No se encontraron problemas de rendimiento!")
            return
            
        # Agrupar por tipo
        issues_by_type = {}
        for issue in self.issues:
            issue_type = issue['type']
            if issue_type not in issues_by_type:
                issues_by_type[issue_type] = []
            issues_by_type[issue_type].append(issue)
            
        # Mostrar por tipo
        for issue_type, issues in issues_by_type.items():
            print(f"\n🔴 {issue_type.upper()} ({len(issues)} problemas)")
            print("-" * 40)
            
            for issue in issues[:5]:  # Mostrar solo los primeros 5
                print(f"📁 {issue['file']}:{issue['line']}")
                print(f"   Problema: {issue['issue']}")
                print(f"   💡 Sugerencia: {issue['suggestion']}")
                print()
                
        # Resumen
        print(f"\n📊 RESUMEN:")
        print(f"   Total de problemas encontrados: {len(self.issues)}")
        
        # Prioridades
        high_priority = [i for i in self.issues if 'N+1' in i['issue'] or 'objects.all()' in i['issue']]
        medium_priority = [i for i in self.issues if 'cache' in i['issue'].lower()]
        
        print(f"   🔥 Prioridad ALTA: {len(high_priority)} (problemas de base de datos)")
        print(f"   🟡 Prioridad MEDIA: {len(medium_priority)} (problemas de caché)")
        print(f"   🟢 Prioridad BAJA: {len(self.issues) - len(high_priority) - len(medium_priority)}")
        
        print(f"\n💡 RECOMENDACIONES PRINCIPALES:")
        print("   1. Optimizar consultas de base de datos (usar select_related, prefetch_related)")
        print("   2. Implementar sistema de caché Redis")
        print("   3. Usar paginación en listas largas")
        print("   4. Comprimir archivos estáticos")
        print("   5. Implementar middleware de rendimiento")


def run_analysis():
    """Función principal para ejecutar el análisis"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)  # Subir un nivel desde scripts/
    
    analyzer = DjangoPerformanceAnalyzer(project_root)
    analyzer.analyze_all()


if __name__ == "__main__":
    run_analysis()
