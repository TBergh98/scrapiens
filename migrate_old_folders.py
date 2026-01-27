"""
Script per migrare i vecchi output folder in una struttura date-stamped.

Questo script:
1. Trova le cartelle "vecchio stile" (01_scrape, 02_deduplicate, ecc.)
2. Determina la data più recente dai file contenuti
3. Crea un folder datato e sposta le cartelle lì dentro
4. Mantiene seen_urls.json fuori dalla migrazione
"""

import sys
from pathlib import Path
from datetime import datetime
import shutil

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger

logger = get_logger(__name__)

OLD_FOLDERS = [
    '01_scrape',
    '02_deduplicate',
    '03_classify',
    '04_extract',
    '05_match_keywords',
    '06_digests'
]

def find_most_recent_modification_date(folder: Path) -> datetime:
    """Trova la data di modifica più recente in una cartella."""
    if not folder.exists():
        return datetime.min
    
    most_recent = datetime.fromtimestamp(folder.stat().st_mtime)
    
    for item in folder.rglob('*'):
        if item.is_file():
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if mtime > most_recent:
                most_recent = mtime
    
    return most_recent

def migrate_old_folders(intermediate_dir: Path, dry_run: bool = True):
    """
    Migra i folder vecchio stile in un folder datato.
    
    Args:
        intermediate_dir: Path to intermediate_outputs/
        dry_run: Se True, mostra solo cosa farebbe senza eseguire
    """
    logger.info("=" * 60)
    logger.info("Migrazione Folder Vecchio Stile → Date-Stamped")
    logger.info("=" * 60)
    
    # Controlla quali folder vecchi esistono
    existing_old_folders = []
    for folder_name in OLD_FOLDERS:
        folder_path = intermediate_dir / folder_name
        if folder_path.exists():
            existing_old_folders.append(folder_name)
    
    if not existing_old_folders:
        logger.info("✅ Nessun folder vecchio stile trovato. Migrazione non necessaria.")
        return
    
    logger.info(f"\n📁 Trovati {len(existing_old_folders)} folder da migrare:")
    for folder in existing_old_folders:
        logger.info(f"  - {folder}")
    
    # Trova la data di modifica più recente
    most_recent_date = datetime.min
    for folder_name in existing_old_folders:
        folder_path = intermediate_dir / folder_name
        folder_mtime = find_most_recent_modification_date(folder_path)
        logger.info(f"\n📅 {folder_name}: ultima modifica {folder_mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        if folder_mtime > most_recent_date:
            most_recent_date = folder_mtime
    
    # Determina il nome del folder datato
    date_folder_name = most_recent_date.strftime('%Y%m%d')
    date_folder_path = intermediate_dir / date_folder_name
    
    logger.info(f"\n🎯 Folder di destinazione: {date_folder_name}")
    logger.info(f"   (basato sulla modifica più recente: {most_recent_date.strftime('%Y-%m-%d')})")
    
    # Controlla se il folder datato esiste già
    if date_folder_path.exists():
        logger.warning(f"\n⚠️  Il folder {date_folder_name}/ esiste già!")
        logger.warning("   La migrazione sovrascriverà il contenuto esistente.")
        
        if not dry_run:
            response = input("\n   Continuare? (y/N): ").strip().lower()
            if response not in ['y', 'yes', 's', 'si', 'sì']:
                logger.info("❌ Migrazione annullata")
                return
    
    # Piano di migrazione
    logger.info(f"\n📋 Piano di migrazione:")
    for folder_name in existing_old_folders:
        source = intermediate_dir / folder_name
        dest = date_folder_path / folder_name
        logger.info(f"   {folder_name}/ → {date_folder_name}/{folder_name}/")
    
    if dry_run:
        logger.info("\n⚠️  MODALITÀ DRY-RUN: Nessuna operazione eseguita")
        logger.info("   Per eseguire la migrazione, lancia:")
        logger.info("   python migrate_old_folders.py --execute")
        return
    
    # Esegui migrazione
    logger.info(f"\n🚀 Esecuzione migrazione...")
    date_folder_path.mkdir(parents=True, exist_ok=True)
    
    for folder_name in existing_old_folders:
        source = intermediate_dir / folder_name
        dest = date_folder_path / folder_name
        
        try:
            # Se la destinazione esiste già, rimuovila
            if dest.exists():
                shutil.rmtree(dest)
            
            # Sposta il folder
            shutil.move(str(source), str(dest))
            logger.info(f"✅ Migrato: {folder_name}/")
        except Exception as e:
            logger.error(f"❌ Errore migrando {folder_name}: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ Migrazione completata!")
    logger.info("=" * 60)
    logger.info(f"\n📁 I vecchi folder sono ora in: intermediate_outputs/{date_folder_name}/")
    logger.info("📝 Il file seen_urls.json è rimasto nella root (cross-run tracking)")
    logger.info("\n💡 I nuovi run creeranno automaticamente folder datati separati.")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Migra i folder vecchio stile in struttura date-stamped"
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Esegui la migrazione (default: dry-run)'
    )
    parser.add_argument(
        '--intermediate-dir',
        type=str,
        default='intermediate_outputs',
        help='Path to intermediate_outputs directory'
    )
    
    args = parser.parse_args()
    
    intermediate_dir = Path(args.intermediate_dir)
    
    if not intermediate_dir.exists():
        logger.error(f"❌ Directory non trovata: {intermediate_dir}")
        return 1
    
    migrate_old_folders(intermediate_dir, dry_run=not args.execute)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
