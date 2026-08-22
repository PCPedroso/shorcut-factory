import sys
import os

# Adiciona a raiz do projeto ao sys.path para importação de 'core' nos testes
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
