import zipfile
import os
import requests
import py7zr
import pandas as pd
import json
from tqdm import tqdm
import time
import sys
import bu_dump
import datetime
import time

def formatted_time(s):
    return str(datetime.timedelta(seconds=round(s)))

def download_file_with_progress_bar(link):
    
    headers = {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0"
    }

    r = requests.get(link, headers=headers, stream=True)

    total_size_in_bytes= int(r.headers.get('content-length', 0))
    block_size = 1024 #1 Kibibyte
    progress_bar = tqdm(total=total_size_in_bytes, unit='iB', unit_scale=True)
    
    filename = link.split('/')[-1]
    with open(filename, 'wb') as file:
        for data in r.iter_content(block_size):
            progress_bar.update(len(data))
            file.write(data)
    progress_bar.close()
    file.close()
    if total_size_in_bytes != 0 and progress_bar.n != total_size_in_bytes:
        print("ERROR, something went wrong")

def load_municipios_json(logjez_files,uf):
    
    first_logjez_filename = logjez_files[0]
    
    container = int(first_logjez_filename.split('-')[0][1:])
    if container == 406:
        eleicao_id = 544
    elif container == 407:
        eleicao_id = 545
    
    uf = uf.lower()
    link = f"https://resultados.tse.jus.br/oficial/ele2022/arquivo-urna/{container}/config/{uf}/{uf}-p000{container}-cs.json"
    filename_json = link.split('/')[-1]    

    print(f"downloading {filename_json}", end=" ")
    r = requests.get(link)

    
    dir_and_filename_json = os.path.join('temp', filename_json)
    
    json_string = r.content
    j = json.loads(json_string)
    
    # print(j)
    
    municipios = {}
    for mun_item in j["abr"][0]["mu"]:
        mun_id = mun_item["cd"]
        mun_name = mun_item["nm"]
        municipios[mun_id]=mun_name
        
    print("[done!]")    
        
    return municipios

def get_all_zip_in_folder():

    filenames = []
    for filename in os.listdir():
        if filename[0:31] == 'bu_imgbu_logjez_rdv_vscmr_2022_':
            if filename[-4:] == '.zip':
                if len(filename) == 40:
                    filenames.append(filename)
                    
    return filenames


def create_csv(filename_zip):
    
    data = {}
    data["uf"] = []
    data["municipio"] = []
    data["cod_municipio"] = []
    data["zona"] = []
    data["secao"] = []
    data["modelo_urna"] = []
    
    data["22"] = []
    data["13"] = []
    data["branco"] = []
    data["nulo"] = []
    data["comparecimentos"] = []
    data["aptos"] = []
     
    if not os.path.exists('temp'):
        os.mkdir('temp')
        
    uf = filename_zip[-6:-4]
    turno = filename_zip[-9]
    
    zipArchive = zipfile.ZipFile(filename_zip)
    zipFileList = zipArchive.namelist()
    
    logjez_files = []
    
    for file in zipFileList:
        if file.split('.')[-1] == 'logjez':
            if file[6] == '-':
                logjez_files.append(file)
    logjez_files.sort()
    
    municipios = load_municipios_json(logjez_files,uf)
    
    print(f"reading {filename_zip}")
    count=0
    length = len(logjez_files)
    start_time = time.time()
    for filename_logjez in logjez_files:
        count+=1
        
        # ler LOGJEZ
        
        file_logjez = zipArchive.open(filename_logjez)
        
        py7zr.SevenZipFile(file_logjez).extract(targets='logd.dat',path='temp')
        folder_and_file_of_dat = os.path.join('temp', 'logd.dat')
    
        s = '?'
        with open(folder_and_file_of_dat, 'r', encoding='cp1252') as f:
            s = f.read()
            f.close()
        
        try:
            a = s.index('Modelo de Urna:')
            modelo = s[a+16:a+22].strip()
        except:
           modelo = '?'
        
        os.remove(folder_and_file_of_dat)
        file_logjez.close()
        
        s = filename_logjez.split('-')[-1].split('.')[0]
        mun_id = s[0:5]
        zon_id = s[5:9]
        sec_id = s[9:13]
        
        mun_name = municipios[mun_id]
        
        data["uf"].append(uf.upper())
        data["municipio"].append(mun_name)
        data["cod_municipio"].append(mun_id)
        data["zona"].append(zon_id)
        data["secao"].append(sec_id)
        data["modelo_urna"].append(modelo)
        
        # ler BU
        
        data_22 = 0
        data_13 = 0
        data_nulo = 0
        data_branco = 0
        qtdComparecimento = 0
        qtdEleitoresAptos = 0
        
        try:
            filename_bu = filename_logjez.split('.')[0] + '.bu'
            zipArchive.extract(filename_bu, 'temp')
        except:
            filename_bu = filename_logjez.split('.')[0] + '.busa'
            zipArchive.extract(filename_bu, 'temp')
            
        folder_and_filename_bu = os.path.join('temp',filename_bu)
        bud = bu_dump.processa_bu(['bu.asn1'],folder_and_filename_bu)
        os.remove(folder_and_filename_bu)
        
        index = 0
        for i in range(len(bud["resultadosVotacaoPorEleicao"])):
            tipo = bud["resultadosVotacaoPorEleicao"][i]["resultadosVotacao"][0]["totaisVotosCargo"][0]["codigoCargo"][1]
            if tipo == 'presidente':
                index = i
        
        qtdEleitoresAptos = bud["resultadosVotacaoPorEleicao"][index]["qtdEleitoresAptos"]
        qtdComparecimento = bud["resultadosVotacaoPorEleicao"][index]["resultadosVotacao"][0]["qtdComparecimento"]
        blocos_de_partidos = bud["resultadosVotacaoPorEleicao"][index]["resultadosVotacao"][0]["totaisVotosCargo"][0]["votosVotaveis"]
        
        for bloco in blocos_de_partidos:
            tipoVoto = bloco["tipoVoto"]
            if tipoVoto == 'nominal':
                partido = bloco["identificacaoVotavel"]["partido"]
            else:
                partido = tipoVoto
        
            quandidadeVotos = bloco["quantidadeVotos"]
        
            if partido == 22:
                data_22 = quandidadeVotos
        
            if partido == 13:
                data_13 = quandidadeVotos
        
            if partido == 'nulo':
                data_nulo = quandidadeVotos
                
            if partido == 'branco':
                data_branco = quandidadeVotos
        
        data["22"].append(data_22)
        data["13"].append(data_13)
        data["nulo"].append(data_nulo)
        data["branco"].append(data_branco)
        data["comparecimentos"].append(qtdComparecimento)
        data["aptos"].append(qtdEleitoresAptos)
        
        # PRINT
        
        actual_time = time.time()
        elapsed_time = actual_time - start_time
        time_by_loop = elapsed_time/count
        remaining_time = time_by_loop*(length-count)
        remaining_str = formatted_time(remaining_time)
        
        print(f"\r seção {count}/{length}, modelo: {modelo}, z{zon_id}/s{sec_id} {mun_name:<30} [remaining {remaining_str}]", end="")
        time.sleep(0.001)
        
    csv_filename = filename_zip.split('.')[0] + '.csv'
    
    print('')
    print(f"creating {csv_filename}", end=" ")
    df = pd.DataFrame(data) 
    df.to_csv(csv_filename)
    print("[done!]")
    
    zipArchive.close()

def load_links():
    with open('links.txt') as f:
        lines = f.readlines()
    return lines

def remove_file(dir_and_file,count=0):
    
    try:
        os.remove(dir_and_file)
    except:
        count +=1
        if count < 7:
            print(f"waiting 10 secods to delete file {dir_and_file}")
            sleep(10)
            remove_file(dir_and_file,count)
        else:
            print(f"could not delete file {dir_and_file}")

def do(skip_link_if_csv_exists=True, overwrite_zip=False, delete_zip_after_reading=False,args=sys.argv):
    
    if len(args) == 1:
        links = load_links()
    else:
        turno = args[1]
        uf = args[2].upper()
        link = f"https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2022/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2022_{turno}t_{uf}.zip"
        links = [link]
        
    for link in links:
        
        link = link.strip()
        filename_zip = link.split('/')[-1]
        filename_csv = filename_zip.split('.')[0] + '.csv'
        
        if os.path.exists(filename_csv) & skip_link_if_csv_exists:
            continue
        
        print('---------------------------------------')
        
        if (not os.path.exists(filename_zip)) or overwrite_zip:
            print(f"downloading {link}")
            print('')
            time.sleep(0.001)
            download_file_with_progress_bar(link)
            print("[done!]")
        else:
            print(f"file {filename_zip} already downloaded")
        
        create_csv(filename_zip)
        
        if delete_zip_after_reading:
            print(f"deleting {filename_zip}", end=" ")
            remove_file(filename_zip)
            print("[done!]")
            
        
        
# do(True,False,True,sys.args)

do(True,True,True,sys.argv)
        
        
        
        
        
        
        
        
        
        
        
        
        
